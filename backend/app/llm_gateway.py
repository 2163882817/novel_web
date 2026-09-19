"""LLM 网关：封装 OpenAI 兼容 API（DeepSeek/Kimi/豆包/通义/GLM 等均可）"""
import asyncio
import json
import re
import time
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import AsyncIterator, TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from app.crypto import decrypt
from app.database import SessionLocal
from app.models import ApiConfig


T = TypeVar("T")

# 模型请求的重试放在网关层，便于所有调用获得一致的行为。OpenAI SDK 的
# 内部重试关闭，避免一次用户请求被 SDK 与本层的重试叠加放大。
_REQUEST_ATTEMPTS = 3
_RETRY_DELAYS_SECONDS = (1, 2)


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model_name: str
    temperature: float
    context_window: int


def get_config() -> LLMConfig | None:
    """读取已保存的 API 配置；未保存完整时返回 None"""
    with SessionLocal() as db:
        row = db.query(ApiConfig).order_by(ApiConfig.id).first()
    if not row or not row.base_url or not row.api_key_enc or not row.model_name:
        return None
    return LLMConfig(
        base_url=row.base_url,
        api_key=decrypt(row.api_key_enc),
        model_name=row.model_name,
        temperature=row.temperature,
        context_window=row.context_window,
    )


def build_client(cfg: LLMConfig) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key, max_retries=0)


def _is_transient_error(error: Exception) -> bool:
    """判断错误是否值得重试，避免把配置、鉴权和请求格式错误拖慢。"""
    if isinstance(error, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
        return True
    status_code = getattr(error, "status_code", None)
    return status_code in (408, 409, 429) or (isinstance(status_code, int) and status_code >= 500)


async def _request_with_retry(request: Callable[[], Awaitable[T]]) -> T:
    """对上游临时故障进行有限退避重试。"""
    for attempt in range(_REQUEST_ATTEMPTS):
        try:
            return await request()
        except Exception as error:
            if not _is_transient_error(error) or attempt == _REQUEST_ATTEMPTS - 1:
                raise
            await asyncio.sleep(_RETRY_DELAYS_SECONDS[attempt])
    raise RuntimeError("请求重试流程异常结束")  # 仅用于类型检查，正常不可达


_THINK_RE = re.compile(
    r"(?s)^\s*<(?:think|thinking|analysis|reasoning)\b[^>]*>.*?</(?:think|thinking|analysis|reasoning)\s*>"
)

# 用于流式场景：逐片段识别思考标签
_THINK_OPEN_RE = re.compile(r"<(?:think|thinking|analysis|reasoning)\b[^>]*>", re.I)
_THINK_CLOSE_RE = re.compile(r"</(?:think|thinking|analysis|reasoning)\s*>", re.I)


def strip_thinking(text: str) -> str:
    """剥离推理模型位于开头的思考块（如 <think>…</think>），避免泄漏进正文。

    兼容两种形态：
    1. 完整标签（含属性，如 <think> 或 <think model="x">…</think>）；
    2. 只有开始标签、输出被截断而缺少结束标签——此时思考块延伸到文本末尾，
       整体丢弃。
    只处理位于文本开头的思考块；正文中间出现的 <think> 由流式状态机处理。
    """
    if not text:
        return text
    stripped = _THINK_RE.sub("", text)
    if not stripped:
        # 整段都是思考块，剥掉后为空
        return ""
    if stripped == text:
        # 无完整标签：若开头就是开始标签且缺少闭合，思考块延伸到末尾，整体丢弃
        if re.match(r"(?s)^\s*<(?:think|thinking|analysis|reasoning)\b[^>]*>", text):
            return ""
    return stripped


def _extract_completion_text(resp: object) -> str:
    """提取非流式响应正文，兼容 SDK 对象、字典和部分兼容服务的字符串响应。"""
    if isinstance(resp, str):
        text = resp.strip()
        if not text:
            raise ValueError("模型服务返回了空响应")
        # 某些兼容服务会把标准 JSON 响应作为字符串返回。
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, (dict, list)):
            resp = parsed
        elif isinstance(parsed, str):
            text = parsed.strip()
            if not text:
                raise ValueError("模型服务返回了空响应")
            return text
        else:
            # 兼容返回裸模型正文的服务，但明确拒绝明显的错误页面。
            if text.lower().startswith(("<!doctype html", "<html")):
                raise ValueError("模型服务返回了 HTML，可能是 Base URL 或接口路径错误")
            return text

    if isinstance(resp, dict):
        choices = resp.get("choices")
        message = choices[0].get("message") if choices else None
        content = message.get("content") if isinstance(message, dict) else None
    else:
        choices = getattr(resp, "choices", None)
        first = choices[0] if choices else None
        message = getattr(first, "message", None) if first is not None else None
        content = getattr(message, "content", None) if message is not None else None

    if not choices:
        raise ValueError("模型服务返回的不是有效的 OpenAI Chat Completions 格式：缺少 choices")
    if message is None:
        raise ValueError("模型服务返回的不是有效的 OpenAI Chat Completions 格式：缺少 message")
    if not isinstance(content, str):
        raise ValueError("模型服务未返回文本内容")
    return content


async def test_connection(cfg: LLMConfig) -> dict:
    """发送一条最小请求验证连通性"""
    client = build_client(cfg)
    t0 = time.monotonic()
    try:
        resp = await _request_with_retry(lambda: client.chat.completions.create(
            model=cfg.model_name,
            messages=[{"role": "user", "content": "请只回复：连接正常"}],
            max_tokens=10,
        ))
        return {
            "ok": True,
            "reply": _extract_completion_text(resp),
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def _iter_chunks(
    cfg: LLMConfig, messages: list[dict], max_tokens: int
) -> AsyncIterator[str]:
    """共享的底层流式迭代器：逐个产出原始 delta 文本（不做任何清洗）。"""
    client = build_client(cfg)
    stream = await _request_with_retry(lambda: client.chat.completions.create(
        model=cfg.model_name,
        messages=messages,
        temperature=cfg.temperature,
        max_tokens=max_tokens,
        stream=True,
    ))
    if not hasattr(stream, "__aiter__"):
        # 部分兼容服务虽传 stream=True 仍一次性返回完整响应
        yield _extract_completion_text(stream)
        return
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def stream_chat(
    cfg: LLMConfig, messages: list[dict], max_tokens: int = 4096
) -> AsyncIterator[str]:
    """流式对话：逐个产出正文片段，并剥离推理模型的 <think> 思考块。

    流式转发时用 state 机跳过思考标签：处于思考块内（含缺少闭合标签、被截断的情况）
    的片段一律丢弃；</think> 闭合后恢复正常转发。若无任何闭合标签出现，
    则思考块会一直延伸到流结束，正文不会泄漏出来。
    """
    in_think = False
    async for text in _iter_chunks(cfg, messages, max_tokens):
        if not in_think:
            m = _THINK_OPEN_RE.search(text)
            if m:
                # 在正文片段中首次出现开标签：只转发开标签之前的部分
                if m.start() > 0:
                    yield text[: m.start()]
                text = text[m.end():]
                in_think = True
        if in_think:
            end = _THINK_CLOSE_RE.search(text)
            if end:
                text = text[end.end():]
                in_think = False
            else:
                # 仍在思考块内，丢弃本片段剩余部分
                continue
        if text:
            yield text


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise ValueError("模型输出不是合法 JSON")


async def chat(
    cfg: LLMConfig,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> tuple[str, dict | None]:
    """非流式普通对话（用于修稿等长文本输出）。返回 (文本, usage 或 None)。"""
    client = build_client(cfg)
    resp = await _request_with_retry(lambda: client.chat.completions.create(
        model=cfg.model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    ))
    usage = None
    try:
        u = resp.usage
        usage = {"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens}
    except Exception:
        pass
    return strip_thinking(_extract_completion_text(resp)), usage


async def json_chat(
    cfg: LLMConfig,
    messages: list[dict],
    temperature: float = 0.5,
    max_tokens: int = 4096,
) -> tuple[dict, dict | None]:
    """非流式 JSON 对话。先尝试 response_format=json_object，失败则降级为普通模式提取 JSON。
    返回 (解析后的 dict, usage 信息或 None)。"""
    client = build_client(cfg)
    last_err = "未知错误"
    for use_format in (True, False):
        try:
            kwargs = dict(
                model=cfg.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if use_format:
                kwargs["response_format"] = {"type": "json_object"}
            resp = await _request_with_retry(lambda: client.chat.completions.create(**kwargs))
            content = _extract_completion_text(resp)
            usage = None
            try:
                u = resp.usage
                usage = {"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens}
            except Exception:
                pass
            return _extract_json(strip_thinking(content)), usage
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
    raise RuntimeError(f"JSON 对话失败：{last_err}")
