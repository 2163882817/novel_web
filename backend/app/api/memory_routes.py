"""记忆系统：细纲生成 / 一致性校对 / 定稿总结 / 人物卡与伏笔库管理"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import llm_gateway, memory_service
from app.database import SessionLocal
from app.models import (
    Chapter,
    ChapterSummary,
    Character,
    Foreshadowing,
    GenerationLog,
    Novel,
    Volume,
)
from app.schemas import (
    CharacterIn,
    CharacterOut,
    CheckerOut,
    ForeshadowingIn,
    ForeshadowingOut,
    MemoryOut,
    PlannerOut,
    ReviseIn,
    SummarizerOut,
    TitleIn,
    TitlesOut,
    VolumeCreateIn,
    VolumeOutlineOut,
    VolumeOut,
    VolumeSummaryOut,
    VolumeUpdateIn,
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_config():
    cfg = llm_gateway.get_config()
    if not cfg:
        raise HTTPException(status_code=400, detail="请先在「API 配置」保存 base_url / API Key / 模型名")
    return cfg


def _log(db: Session, novel_id, chapter_id, agent, cfg, usage, data) -> None:
    """记录一次 LLM 调用（调用方负责 commit）"""
    pt = usage.get("prompt_tokens", 0) if usage else 0
    ct = usage.get("completion_tokens", 0) if usage else 0
    if not ct and isinstance(data, dict):
        ct = len(str(data)) // 2  # 粗估兜底
    db.add(GenerationLog(
        novel_id=novel_id,
        chapter_id=chapter_id,
        agent_type=agent,
        model_name=cfg.model_name,
        prompt_tokens=pt,
        completion_tokens=ct,
    ))


# ---------- 四步流水线 ----------

@router.post("/novels/{novel_id}/next-outline")
async def generate_outline(novel_id: int, chapter_no: int = 0, db: Session = Depends(get_db)):
    """① 细纲师：规划下一章（或指定章）细纲，不落库，返回给用户确认"""
    cfg = _require_config()
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    if chapter_no <= 0:
        last = (
            db.query(Chapter)
            .filter(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_no.desc())
            .first()
        )
        chapter_no = (last.chapter_no + 1) if last else 1
    messages = memory_service.build_planner_messages(db, novel, chapter_no)
    data, usage = await llm_gateway.json_chat(cfg, messages, temperature=0.7)
    try:
        out = PlannerOut.model_validate(data)
    except ValidationError as e:
        _log(db, novel_id, None, "planner", cfg, usage, data)
        db.commit()
        raise HTTPException(status_code=500, detail=f"细纲 JSON 校验失败：{e}")
    _log(db, novel_id, None, "planner", cfg, usage, data)
    db.commit()
    return {**out.model_dump(), "chapter_no": chapter_no}


@router.post("/chapters/{chapter_id}/check")
async def check_chapter(chapter_id: int, db: Session = Depends(get_db)):
    """③ 校对：检查本章与记忆库的矛盾，返回问题清单"""
    cfg = _require_config()
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.content.strip():
        raise HTTPException(status_code=400, detail="章节内容为空，无法校对")
    novel = db.get(Novel, chapter.novel_id)
    messages = memory_service.build_checker_messages(db, novel, chapter)
    data, usage = await llm_gateway.json_chat(cfg, messages, temperature=0.3)
    try:
        out = CheckerOut.model_validate(data)
    except ValidationError as e:
        _log(db, novel.id, chapter.id, "checker", cfg, usage, data)
        db.commit()
        raise HTTPException(status_code=500, detail=f"校对 JSON 校验失败：{e}")
    _log(db, novel.id, chapter.id, "checker", cfg, usage, data)
    db.commit()
    return out


@router.post("/chapters/{chapter_id}/finalize")
async def finalize_chapter(chapter_id: int, db: Session = Depends(get_db)):
    """④ 总结师：定稿并更新记忆库（章摘要/伏笔/角色状态）"""
    cfg = _require_config()
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.content.strip():
        raise HTTPException(status_code=400, detail="章节内容为空，无法定稿")
    novel = db.get(Novel, chapter.novel_id)
    messages = memory_service.build_summarizer_messages(db, novel, chapter)
    data, usage = await llm_gateway.json_chat(cfg, messages, temperature=0.3)
    try:
        out = SummarizerOut.model_validate(data)
    except ValidationError as e:
        _log(db, novel.id, chapter.id, "summarizer", cfg, usage, data)
        db.commit()
        raise HTTPException(status_code=500, detail=f"总结 JSON 校验失败：{e}")
    memory_service.apply_summary(db, chapter, out.model_dump())
    _log(db, novel.id, chapter.id, "summarizer", cfg, usage, data)
    db.commit()
    return {
        "ok": True,
        "summary": out.summary,
        "characters_updated": len(out.character_state_updates),
        "foreshadowings_planted": len(out.foreshadowings_planted),
        "foreshadowings_resolved": len(out.foreshadowings_resolved),
    }


@router.post("/chapters/{chapter_id}/revise")
async def revise_chapter(chapter_id: int, body: ReviseIn, db: Session = Depends(get_db)):
    """修稿师：按用户勾选的校对问题精准修订，返回完整修订稿（不落库，由前端决定是否应用）"""
    cfg = _require_config()
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.content.strip():
        raise HTTPException(status_code=400, detail="章节内容为空，无法修订")
    if not body.issues:
        raise HTTPException(status_code=400, detail="请勾选要修复的问题")
    novel = db.get(Novel, chapter.novel_id)

    from app.prompts import REVISER_SYSTEM

    ctx = memory_service._common_ctx(db, novel)
    system = REVISER_SYSTEM.format(
        world_setting=novel.world_setting or "未提供",
        characters=ctx["characters"],
        recent_summaries=ctx["recent_summaries"],
        foreshadowings="\n".join(memory_service._all_foreshadowings(db, novel.id)) or "（暂无伏笔）",
        writing_restrictions=ctx["writing_restrictions"],
    )
    issue_lines = []
    for i, it in enumerate(body.issues, 1):
        issue_lines.append(
            f"{i}. [{it.get('type', '')}] {it.get('location', '')}｜问题：{it.get('description', '')}"
            f"｜建议：{it.get('suggestion', '')}"
        )
    user = (
        f"【本章正文】\n{chapter.content}\n\n【待修复问题】\n"
        + "\n".join(issue_lines)
        + "\n\n请输出修订后的完整正文："
    )
    revised, usage = await llm_gateway.chat(
        cfg, [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5, max_tokens=8192,
    )
    _log(db, novel.id, chapter.id, "reviser", cfg, usage, {"chars": len(revised)})
    db.commit()
    return {"content": revised}


@router.post("/titles")
async def gen_titles(body: TitleIn, db: Session = Depends(get_db)):
    """标题师：根据细纲/正文生成候选章节标题（参考本书已有标题风格）"""
    cfg = _require_config()
    novel = None
    if body.novel_id:
        novel = db.get(Novel, body.novel_id)
        if not novel:
            raise HTTPException(status_code=404, detail="小说不存在")
    if not body.content.strip() and not body.outline.strip():
        raise HTTPException(status_code=400, detail="请提供本章正文或细纲")

    from app.prompts import TITLER_SYSTEM

    prev_titles = "（暂无）"
    if novel:
        prevs = (
            db.query(Chapter)
            .filter(Chapter.novel_id == novel.id, Chapter.title != "")
            .order_by(Chapter.chapter_no.desc())
            .limit(5)
            .all()
        )
        if prevs:
            prev_titles = "\n".join(f"第{ch.chapter_no}章 {ch.title}" for ch in reversed(prevs))

    count = max(3, min(body.count, 8))
    system = TITLER_SYSTEM.format(
        title=novel.title if novel else "未命名小说",
        chapter_no=body.chapter_no or 1,
        genre=(novel.genre if novel else "") or "未指定",
        style=(novel.style if novel else "") or "网文节奏",
        prev_titles=prev_titles,
        outline=body.outline.strip() or "未提供",
        content=(body.content.strip() or "未提供")[:6000],
        count=count,
    )
    data, usage = await llm_gateway.json_chat(
        cfg,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"请为第{body.chapter_no or 1}章生成标题。"},
        ],
        temperature=0.9,
    )
    try:
        out = TitlesOut.model_validate(data)
    except ValidationError as e:
        _log(db, novel.id if novel else None, None, "titler", cfg, usage, data)
        db.commit()
        raise HTTPException(status_code=500, detail=f"标题 JSON 校验失败：{e}")
    if not out.titles:
        _log(db, novel.id if novel else None, None, "titler", cfg, usage, data)
        db.commit()
        raise HTTPException(status_code=500, detail="模型未返回候选标题")
    _log(db, novel.id if novel else None, None, "titler", cfg, usage, data)
    db.commit()
    return out


# ---------- 记忆库查询与手工管理 ----------

@router.get("/novels/{novel_id}/memory", response_model=MemoryOut)
def get_memory(novel_id: int, db: Session = Depends(get_db)):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    characters = (
        db.query(Character)
        .filter(Character.novel_id == novel_id)
        .order_by(Character.id)
        .all()
    )
    foreshadowings = (
        db.query(Foreshadowing)
        .filter(Foreshadowing.novel_id == novel_id)
        .order_by(Foreshadowing.updated_at.desc())
        .all()
    )
    summaries = []
    rows = (
        db.query(ChapterSummary)
        .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
        .filter(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_no.desc())
        .all()
    )
    for s in rows:
        ch = db.get(Chapter, s.chapter_id)
        summaries.append({
            "chapter_no": ch.chapter_no,
            "chapter_title": ch.title,
            "summary": s.summary,
            "key_events": s.key_events or [],
            "outline_progress": s.outline_progress,
            "created_at": s.created_at.isoformat(),
        })
    volumes = []
    for v in db.query(Volume).filter(Volume.novel_id == novel_id).order_by(Volume.volume_no).all():
        cnt = db.query(Chapter).filter(Chapter.volume_id == v.id).count()
        volumes.append(VolumeOut(
            id=v.id, volume_no=v.volume_no, title=v.title, outline=v.outline,
            summary=v.summary, status=v.status, chapter_count=cnt,
        ))
    return MemoryOut(
        volumes=volumes,
        characters=characters,
        foreshadowings=foreshadowings,
        summaries=summaries,
        writing_restrictions={
            "has_text": bool(novel.writing_restrictions_text.strip()),
            "length": len(novel.writing_restrictions_text or ""),
        },
    )


@router.put("/volumes/{volume_id}")
def update_volume(volume_id: int, body: VolumeUpdateIn, db: Session = Depends(get_db)):
    v = db.get(Volume, volume_id)
    if not v:
        raise HTTPException(status_code=404, detail="卷不存在")
    if body.title is not None:
        v.title = body.title
    if body.outline is not None:
        v.outline = body.outline
    if body.status is not None:
        v.status = body.status
    db.commit()
    return {"ok": True}


@router.post("/novels/{novel_id}/volume-outline")
async def gen_volume_outline(novel_id: int, db: Session = Depends(get_db)):
    """大纲师：为下一卷生成卷大纲（不落库，供用户确认后创建）"""
    cfg = _require_config()
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")

    from app.prompts import VOLUME_OUTLINER_SYSTEM

    ctx = memory_service._common_ctx(db, novel)
    max_no = (
        db.query(Volume)
        .filter(Volume.novel_id == novel_id)
        .order_by(Volume.volume_no.desc())
        .first()
    )
    volume_no = (max_no.volume_no + 1) if max_no else 1
    system = VOLUME_OUTLINER_SYSTEM.format(
        title=novel.title,
        volume_no=volume_no,
        genre=novel.genre or "未指定",
        style=novel.style or "网文节奏",
        synopsis=novel.synopsis or "未提供",
        recent_summaries=ctx["recent_summaries"],
        prev_volume_summary=ctx["prev_volume_summary"],
        foreshadowings=ctx["pending_foreshadowings"],
        characters=ctx["characters"],
    )
    data, usage = await llm_gateway.json_chat(
        cfg,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"请规划第{volume_no}卷大纲，直接输出 JSON。"},
        ],
        temperature=0.7,
    )
    try:
        out = VolumeOutlineOut.model_validate(data)
    except ValidationError as e:
        _log(db, novel_id, None, "outliner", cfg, usage, data)
        db.commit()
        raise HTTPException(status_code=500, detail=f"卷大纲 JSON 校验失败：{e}")
    _log(db, novel_id, None, "outliner", cfg, usage, data)
    db.commit()
    return {**out.model_dump(), "volume_no": volume_no}


@router.post("/novels/{novel_id}/volumes", response_model=VolumeOut)
def create_volume(novel_id: int, body: VolumeCreateIn, db: Session = Depends(get_db)):
    """开新卷：自动完结上一卷"""
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    max_no = (
        db.query(Volume)
        .filter(Volume.novel_id == novel_id)
        .order_by(Volume.volume_no.desc())
        .first()
    )
    volume_no = (max_no.volume_no + 1) if max_no else 1
    for v in db.query(Volume).filter(Volume.novel_id == novel_id, Volume.status == "连载中").all():
        v.status = "完结"
    v = Volume(
        novel_id=novel_id,
        volume_no=volume_no,
        title=body.title.strip() or f"第{volume_no}卷",
        outline=body.outline,
        status="连载中",
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return VolumeOut(
        id=v.id, volume_no=v.volume_no, title=v.title, outline=v.outline,
        summary=v.summary, status=v.status, chapter_count=0,
    )


@router.post("/volumes/{volume_id}/summary")
async def gen_volume_summary(volume_id: int, db: Session = Depends(get_db)):
    """卷总结员：根据本卷各章摘要生成卷摘要并落库（含关键发展与遗留悬念）"""
    cfg = _require_config()
    volume = db.get(Volume, volume_id)
    if not volume:
        raise HTTPException(status_code=404, detail="卷不存在")
    novel = db.get(Novel, volume.novel_id)

    from app.prompts import VOLUME_SUMMARIZER_SYSTEM

    rows = (
        db.query(ChapterSummary)
        .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
        .filter(Chapter.volume_id == volume_id)
        .order_by(Chapter.chapter_no)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=400, detail="该卷还没有定稿章节的摘要，请先在工作台完成章节定稿")
    chapter_text = "\n".join(
        f"第{db.get(Chapter, s.chapter_id).chapter_no}章：{s.summary}" for s in rows
    )
    user = f"【卷大纲】\n{volume.outline or '未提供'}\n\n【本卷各章摘要】\n{chapter_text}"
    data, usage = await llm_gateway.json_chat(
        cfg,
        [
            {"role": "system", "content": VOLUME_SUMMARIZER_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=8192,
    )
    try:
        out = VolumeSummaryOut.model_validate(data)
    except ValidationError as e:
        _log(db, novel.id, None, "volume_summarizer", cfg, usage, data)
        db.commit()
        raise HTTPException(status_code=500, detail=f"卷摘要 JSON 校验失败：{e}")
    # 关键发展与遗留悬念一并存入 summary，供细纲师/大纲师承接
    parts = [out.summary.strip()]
    if out.key_developments:
        parts.append("【关键剧情发展】\n" + "\n".join(f"- {k}" for k in out.key_developments))
    if out.unresolved:
        parts.append("【遗留悬念（下一卷承接）】\n" + "\n".join(f"- {u}" for u in out.unresolved))
    volume.summary = "\n\n".join(parts)
    _log(db, novel.id, None, "volume_summarizer", cfg, usage, data)
    db.commit()
    return {"ok": True, "summary": volume.summary}


@router.post("/novels/{novel_id}/characters", response_model=CharacterOut)
def create_character(novel_id: int, body: CharacterIn, db: Session = Depends(get_db)):
    if not db.get(Novel, novel_id):
        raise HTTPException(status_code=404, detail="小说不存在")
    c = Character(novel_id=novel_id, name=body.name.strip(), role=body.role, card=body.card)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/characters/{character_id}", response_model=CharacterOut)
def update_character(character_id: int, body: CharacterIn, db: Session = Depends(get_db)):
    c = db.get(Character, character_id)
    if not c:
        raise HTTPException(status_code=404, detail="人物卡不存在")
    c.name = body.name.strip()
    c.role = body.role
    c.card = body.card
    db.commit()
    db.refresh(c)
    return c


@router.delete("/characters/{character_id}")
def delete_character(character_id: int, db: Session = Depends(get_db)):
    c = db.get(Character, character_id)
    if not c:
        raise HTTPException(status_code=404, detail="人物卡不存在")
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/novels/{novel_id}/foreshadowings", response_model=ForeshadowingOut)
def create_foreshadowing(novel_id: int, body: ForeshadowingIn, db: Session = Depends(get_db)):
    if not db.get(Novel, novel_id):
        raise HTTPException(status_code=404, detail="小说不存在")
    f = Foreshadowing(
        novel_id=novel_id,
        title=body.title.strip(),
        description=body.description,
        status=body.status,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.put("/foreshadowings/{foreshadowing_id}", response_model=ForeshadowingOut)
def update_foreshadowing(foreshadowing_id: int, body: ForeshadowingIn, db: Session = Depends(get_db)):
    f = db.get(Foreshadowing, foreshadowing_id)
    if not f:
        raise HTTPException(status_code=404, detail="伏笔不存在")
    f.title = body.title.strip()
    f.description = body.description
    f.status = body.status
    db.commit()
    db.refresh(f)
    return f


@router.delete("/foreshadowings/{foreshadowing_id}")
def delete_foreshadowing(foreshadowing_id: int, db: Session = Depends(get_db)):
    f = db.get(Foreshadowing, foreshadowing_id)
    if not f:
        raise HTTPException(status_code=404, detail="伏笔不存在")
    db.delete(f)
    db.commit()
    return {"ok": True}
