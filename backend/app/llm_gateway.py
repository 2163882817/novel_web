"""LLM 网关：封装 OpenAI 兼容 API（DeepSeek/Kimi/豆包/通义/GLM 等均可）"""
import json
import re
import time
from dataclasses import dataclass
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.crypto import decrypt
from app.database import SessionLocal
from app.models import ApiConfig


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
    return AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key, max_retries=2)


async def test_connection(cfg: LLMConfig) -> dict:
    """发送一条最小请求验证连通性"""
    client = build_client(cfg)
    t0 = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=cfg.model_name,
            messages=[{"role": "user", "content": "请只回复：连接正常"}],
            max_tokens=10,
        )
        return {
            "ok": True,
            "reply": resp.choices[0].message.content,
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def stream_chat(
    cfg: LLMConfig, messages: list[dict], max_tokens: int = 4096
) -> AsyncIterator[str]:
    """流式对话：逐个产出正文片段；网络层异常直接抛出由调用方处理"""
    client = build_client(cfg)
    stream = await client.chat.completions.create(
        model=cfg.model_name,
        messages=messages,
        temperature=cfg.temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


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
    resp = await client.chat.completions.create(
        model=cfg.model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    usage = None
    try:
        u = resp.usage
        usage = {"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens}
    except Exception:
        pass
    return resp.choices[0].message.content or "", usage


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
            resp = await client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            usage = None
            try:
                u = resp.usage
                usage = {"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens}
            except Exception:
                pass
            return _extract_json(content), usage
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
    raise RuntimeError(f"JSON 对话失败：{last_err}")
