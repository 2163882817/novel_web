"""单章写作：SSE 流式输出；novel_id 模式下由记忆服务组装完整上下文"""
import asyncio
import json
import re
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import llm_gateway, memory_service, prompts
from app.database import SessionLocal
from app.models import Chapter, GenerationLog, Novel
from app.schemas import VariantsOut, WriteRequest

router = APIRouter()

_VARIANT_INSTRUCTIONS = {
    "A": "采用电影感强的场景推进：动作、环境与对话交替，节奏明快，突出冲突和章末钩子。",
    "B": "采用人物心理与细腻情绪推进：强化人物选择、情感变化和潜台词，但严格完成相同事件。",
    "C": "采用悬念与氛围推进：控制信息释放，增加画面感和阅读张力，但不得改变事件顺序、因果和结局。",
}



async def _variant_messages(req: WriteRequest, label: str, novel_id: int | None, chapter_no: int, previous_text: str):
    with SessionLocal() as db:
        novel = db.get(Novel, novel_id) if novel_id else None
        if novel_id and not novel:
            raise HTTPException(status_code=404, detail="小说不存在")
        if novel:
            req.title = novel.title
            req.genre = req.genre or novel.genre
            req.style = req.style or novel.style
            req.protagonist = req.protagonist or novel.protagonist
            req.world_setting = req.world_setting or novel.world_setting
            req.synopsis = req.synopsis or novel.synopsis
            req.writing_restrictions = novel.writing_restrictions_text or ""
            messages = memory_service.build_writer_messages(db, novel, req, chapter_no, previous_text)
        else:
            messages = prompts.build_standalone_messages(req)
    messages.append({
        "role": "user",
        "content": (
            f"这是正文版本 {label}。{_VARIANT_INSTRUCTIONS[label]}\n"
            "三版必须严格共享同一章细纲的剧情主线、人物目标、关键事件、因果关系和章末结果；"
            "只改变叙事表达，不得增删或改写主线事件。只输出正文 Markdown，不要解释。"
        ),
    })
    return messages


@router.post("/write/variants", response_model=VariantsOut)
async def write_variants(req: WriteRequest):
    cfg = llm_gateway.get_config()
    if not cfg:
        raise HTTPException(status_code=400, detail="请先在「API 配置」保存 base_url / API Key / 模型名")

    t0 = time.monotonic()
    novel_id = req.novel_id
    chapter_no = req.chapter_no
    previous_text = req.previous_text
    if novel_id:
        with SessionLocal() as db:
            novel = db.get(Novel, novel_id)
            if not novel:
                raise HTTPException(status_code=404, detail="小说不存在")
            if chapter_no <= 0:
                last = db.query(Chapter).filter(Chapter.novel_id == novel.id).order_by(Chapter.chapter_no.desc()).first()
                chapter_no = (last.chapter_no + 1) if last else 1
            if not previous_text:
                prev = db.query(Chapter).filter(
                    Chapter.novel_id == novel.id, Chapter.chapter_no < chapter_no
                ).order_by(Chapter.chapter_no.desc()).first()
                if prev and prev.content:
                    previous_text = prev.content[-800:]
    elif chapter_no <= 0:
        chapter_no = 1

    async def generate(label):
        messages = await _variant_messages(req.model_copy(deep=True), label, novel_id, chapter_no, previous_text)
        content, usage = await llm_gateway.chat(cfg, messages, temperature=cfg.temperature, max_tokens=req.max_tokens)
        return {"label": label, "content": content, "word_count": len(re.sub(r"\\s", "", content)), "usage": usage}

    results = await asyncio.gather(*(generate(label) for label in ("A", "B", "C")))
    duration_ms = int((time.monotonic() - t0) * 1000)
    with SessionLocal() as db:
        for result in results:
            usage = result.pop("usage") or {}
            db.add(GenerationLog(
                novel_id=novel_id,
                agent_type=f"writer_{result['label']}",
                model_name=cfg.model_name,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                duration_ms=duration_ms,
                status="成功",
            ))
        db.commit()
    return {"variants": results, "duration_ms": duration_ms}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/write/stream")
async def write_stream(req: WriteRequest):
    cfg = llm_gateway.get_config()
    if not cfg:
        raise HTTPException(
            status_code=400, detail="请先在「API 配置」保存 base_url / API Key / 模型名"
        )

    # 组装上下文（小说设定 + 人物卡 + 前情摘要 + 待回收伏笔 + 细纲 + 上一章结尾）
    with SessionLocal() as db:
        novel = None
        previous_text = req.previous_text
        chapter_no = req.chapter_no
        chapter_id = None

        if req.novel_id:
            novel = db.get(Novel, req.novel_id)
            if not novel:
                raise HTTPException(status_code=404, detail="小说不存在")
            req.title = novel.title
            req.genre = req.genre or novel.genre
            req.style = req.style or novel.style
            req.protagonist = req.protagonist or novel.protagonist
            req.world_setting = req.world_setting or novel.world_setting
            req.synopsis = req.synopsis or novel.synopsis
            req.writing_restrictions = novel.writing_restrictions_text or ""
            if chapter_no <= 0:
                last = (
                    db.query(Chapter)
                    .filter(Chapter.novel_id == novel.id)
                    .order_by(Chapter.chapter_no.desc())
                    .first()
                )
                chapter_no = (last.chapter_no + 1) if last else 1
            if not previous_text:
                prev = (
                    db.query(Chapter)
                    .filter(Chapter.novel_id == novel.id, Chapter.chapter_no < chapter_no)
                    .order_by(Chapter.chapter_no.desc())
                    .first()
                )
                if prev and prev.content:
                    previous_text = prev.content[-800:]
            messages = memory_service.build_writer_messages(db, novel, req, chapter_no, previous_text)
            chapter_id = (
                db.query(Chapter.id)
                .filter(Chapter.novel_id == novel.id, Chapter.chapter_no == chapter_no)
                .scalar()
            )
        else:
            if chapter_no <= 0:
                chapter_no = 1
            req.chapter_no = chapter_no
            messages = prompts.build_standalone_messages(req)

        novel_id = req.novel_id

    async def gen():
        t0 = time.monotonic()
        total_chars = 0
        status, error = "成功", ""
        try:
            async for text in llm_gateway.stream_chat(cfg, messages, max_tokens=req.max_tokens):
                total_chars += len(text)
                yield _sse({"type": "delta", "text": text})
        except Exception as e:
            status, error = "失败", f"{type(e).__name__}: {e}"
            yield _sse({"type": "error", "message": error})
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            yield _sse({
                "type": "done",
                "chars": total_chars,
                "duration_ms": duration_ms,
                "status": status,
            })
            # 落日志（token 粗估：中文约 1 字 ≈ 1~2 token，按字符数折半）
            with SessionLocal() as db:
                db.add(GenerationLog(
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    agent_type="writer",
                    model_name=cfg.model_name,
                    completion_tokens=total_chars // 2,
                    duration_ms=duration_ms,
                    status=status,
                    error=error,
                ))
                db.commit()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
