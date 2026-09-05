"""分层记忆服务：上下文组装（写第 N 章只带必要记忆）与记忆更新"""
from sqlalchemy.orm import Session

from app.models import Chapter, ChapterSummary, Character, Foreshadowing, Novel, Volume

_ROLE_ORDER = {"主角": 0, "反派": 1, "配角": 2}
_NO_CHANGE = {"", "无", "无变化", "none", "None"}
_RESTRICTIONS_CONTEXT_LIMIT = 8000


def _clip_text(text: str, limit: int, notice: str) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = max(1, limit // 2)
    tail = max(1, limit - head)
    marker = f"\n\n（{notice}）\n\n"
    available = max(2, limit - len(marker))
    head = available // 2
    tail = available - head
    return text[:head] + marker + text[-tail:]


def _recent_summaries(db: Session, novel_id: int, limit: int = 3) -> list[str]:
    rows = (
        db.query(ChapterSummary)
        .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
        .filter(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_no.desc())
        .limit(limit)
        .all()
    )
    out = []
    for s in reversed(rows):  # 最早在前
        ch = db.get(Chapter, s.chapter_id)
        out.append(f"第{ch.chapter_no}章：{s.summary}" if ch else s.summary)
    return out


def _pending_foreshadowings(db: Session, novel_id: int, limit: int = 10) -> list[str]:
    rows = (
        db.query(Foreshadowing)
        .filter(Foreshadowing.novel_id == novel_id, Foreshadowing.status == "待回收")
        .order_by(Foreshadowing.created_at)
        .limit(limit)
        .all()
    )
    out = []
    for f in rows:
        if f.planted_chapter_id:
            ch = db.get(Chapter, f.planted_chapter_id)
            where = f"（埋设于第{ch.chapter_no}章）" if ch else ""
        else:
            where = "（手工登记）"
        out.append(f"「{f.title}」{where}：{f.description}")
    return out


def _all_foreshadowings(db: Session, novel_id: int) -> list[str]:
    rows = (
        db.query(Foreshadowing)
        .filter(Foreshadowing.novel_id == novel_id)
        .order_by(Foreshadowing.created_at)
        .all()
    )
    out = []
    for f in rows:
        planted = db.get(Chapter, f.planted_chapter_id) if f.planted_chapter_id else None
        resolved = db.get(Chapter, f.resolved_chapter_id) if f.resolved_chapter_id else None
        where = f"埋设于第{planted.chapter_no}章" if planted else "手工登记"
        when = f"第{resolved.chapter_no}章" if resolved else "未回收"
        out.append(f"「{f.title}」[{f.status}] {where}，回收于{when}：{f.description}")
    return out


def _character_briefs(db: Session, novel_id: int, limit: int = 6) -> list[str]:
    rows = db.query(Character).filter(Character.novel_id == novel_id).all()
    rows.sort(key=lambda c: (_ROLE_ORDER.get(c.role, 3), c.id))
    out = []
    for c in rows[:limit]:
        if c.raw_profile:
            # 导入的人物卡原文优先：这是作者亲手写的人设约束
            rp = c.raw_profile.strip()
            if len(rp) > 1200:
                rp = rp[:1200] + "\n（人物卡过长已截断）"
            out.append(f"## {c.name}（{c.role}）\n{rp}")
            continue
        card = c.card or {}
        bits = [f"{c.name}（{c.role}）"]
        for k in ("外貌", "性格", "目标", "位置", "关系", "情感"):
            if card.get(k):
                bits.append(f"{k}：{card[k]}")
        out.append("；".join(bits))
    return out


def _current_volume(db: Session, novel_id: int) -> Volume | None:
    return (
        db.query(Volume)
        .filter(Volume.novel_id == novel_id)
        .order_by(Volume.volume_no.desc())
        .first()
    )


def _common_ctx(db: Session, novel: Novel) -> dict:
    volume = _current_volume(db, novel.id)
    # 前卷摘要：最近一个有摘要的已完结卷（供开新卷初期衔接）
    prev_volume_summary = "（暂无）"
    prev = (
        db.query(Volume)
        .filter(Volume.novel_id == novel.id, Volume.summary != "")
        .order_by(Volume.volume_no.desc())
        .first()
    )
    if prev:
        prev_volume_summary = prev.summary
    outline = volume.outline if volume and volume.outline else "未提供，请依据全书简介与前情摘要推进主线"
    if len(outline) > 6000:
        outline = outline[:6000] + "\n（大纲过长已截断，优先完成已给出的阶段）"
    # 导入的设定约束（故事圣经/全书总纲）
    bible = novel.story_bible_text or ""
    if len(bible) > 5000:
        bible = bible[:5000] + "\n（圣经过长已截断）"
    book_rules = novel.book_outline_text or ""
    if len(book_rules) > 3000:
        book_rules = book_rules[:3000] + "\n（总纲过长已截断）"
    restrictions = _clip_text(
        novel.writing_restrictions_text,
        _RESTRICTIONS_CONTEXT_LIMIT,
        "限制词文档过长，中间内容已截断，首尾规则保留",
    )
    return {
        "characters": "\n".join(_character_briefs(db, novel.id)) or "（暂无人物卡）",
        "recent_summaries": "\n".join(_recent_summaries(db, novel.id)) or "（暂无前情摘要）",
        "pending_foreshadowings": "\n".join(_pending_foreshadowings(db, novel.id))
        or "（暂无待回收伏笔）",
        "volume_outline": outline,
        "prev_volume_summary": prev_volume_summary,
        "story_bible": bible or "（未导入故事圣经）",
        "book_rules": book_rules or "（未导入全书总纲）",
        "writing_restrictions": restrictions or "（未导入 AI 写作限制词文档）",
    }


# ---------- 四角色消息组装 ----------

def build_planner_messages(db: Session, novel: Novel, chapter_no: int) -> list[dict]:
    from app.prompts import PLANNER_SYSTEM

    ctx = _common_ctx(db, novel)
    system = PLANNER_SYSTEM.format(
        title=novel.title,
        chapter_no=chapter_no,
        genre=novel.genre or "未指定",
        style=novel.style or "流畅自然、网文节奏",
        synopsis=novel.synopsis or "未提供",
        volume_outline=ctx["volume_outline"],
        prev_volume_summary=ctx["prev_volume_summary"],
        story_bible=ctx["story_bible"],
        book_rules=ctx["book_rules"],
        recent_summaries=ctx["recent_summaries"],
        foreshadowings=ctx["pending_foreshadowings"],
        characters=ctx["characters"],
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"请规划第{chapter_no}章细纲，直接输出 JSON。"},
    ]


def build_writer_messages(
    db: Session, novel: Novel, req, chapter_no: int, previous_text: str
) -> list[dict]:
    from app.prompts import WRITER_SYSTEM

    ctx = _common_ctx(db, novel)
    system = WRITER_SYSTEM.format(
        title=novel.title,
        chapter_no=chapter_no,
        style=novel.style or "流畅自然、网文节奏",
        world_setting=novel.world_setting or "未指定，可合理发挥",
        synopsis=novel.synopsis or "未提供",
        story_bible=ctx["story_bible"],
        characters=ctx["characters"],
        recent_summaries=ctx["recent_summaries"],
        foreshadowings=ctx["pending_foreshadowings"],
        writing_restrictions=ctx["writing_restrictions"],
        outline=req.outline or "未提供，请自行安排本章节奏",
        previous_text=previous_text or "本章是第一章，无需衔接",
    )
    return [{"role": "system", "content": system}]


def build_checker_messages(db: Session, novel: Novel, chapter: Chapter) -> list[dict]:
    from app.prompts import CHECKER_SYSTEM

    ctx = _common_ctx(db, novel)
    system = CHECKER_SYSTEM.format(
        characters=ctx["characters"],
        world_setting=novel.world_setting or "未提供",
        story_bible=ctx["story_bible"],
        recent_summaries=ctx["recent_summaries"],
        foreshadowings="\n".join(_all_foreshadowings(db, novel.id)) or "（暂无伏笔）",
        writing_restrictions=ctx["writing_restrictions"],
        outline=chapter.detailed_outline or "未提供",
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"【本章正文】\n{chapter.content}"},
    ]


def build_summarizer_messages(db: Session, novel: Novel, chapter: Chapter) -> list[dict]:
    from app.prompts import SUMMARIZER_SYSTEM

    chars = "\n".join(_character_briefs(db, novel.id, limit=20)) or "（暂无）"
    system = SUMMARIZER_SYSTEM.format(characters=chars)
    content = f"【本章细纲】\n{chapter.detailed_outline or '未提供'}\n\n【本章正文】\n{chapter.content}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]


# ---------- 记忆更新 ----------

def apply_summary(db: Session, chapter: Chapter, data: dict) -> None:
    """将总结师输出写入记忆库：章摘要 / 伏笔埋设与回收 / 角色状态 / 章节定稿。
    调用方负责 commit。"""
    # 1. 章摘要（重复定稿则覆盖）
    old = db.query(ChapterSummary).filter(ChapterSummary.chapter_id == chapter.id).first()
    if old:
        old.summary = data.get("summary", "")
        old.key_events = data.get("key_events", [])
        old.outline_progress = data.get("outline_progress", "")
    else:
        db.add(ChapterSummary(
            chapter_id=chapter.id,
            summary=data.get("summary", ""),
            key_events=data.get("key_events", []),
            outline_progress=data.get("outline_progress", ""),
        ))

    # 2. 新埋伏笔（按标题去重）
    for item in data.get("foreshadowings_planted", []):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        exists = (
            db.query(Foreshadowing)
            .filter(Foreshadowing.novel_id == chapter.novel_id, Foreshadowing.title == title)
            .first()
        )
        if not exists:
            db.add(Foreshadowing(
                novel_id=chapter.novel_id,
                title=title,
                description=str(item.get("description", "")),
                status="待回收",
                planted_chapter_id=chapter.id,
            ))

    # 3. 回收伏笔（标题包含匹配）
    for rtitle in data.get("foreshadowings_resolved", []):
        rtitle = str(rtitle).strip()
        if not rtitle:
            continue
        for f in (
            db.query(Foreshadowing)
            .filter(Foreshadowing.novel_id == chapter.novel_id, Foreshadowing.status != "已回收")
            .all()
        ):
            if rtitle in f.title or f.title in rtitle:
                f.status = "已回收"
                f.resolved_chapter_id = chapter.id
                break

    # 4. 角色状态更新；新角色自动建档
    for u in data.get("character_state_updates", []):
        name = str(u.get("name", "")).strip()
        if not name:
            continue
        c = (
            db.query(Character)
            .filter(Character.novel_id == chapter.novel_id, Character.name == name)
            .first()
        )
        if not c:
            c = Character(
                novel_id=chapter.novel_id,
                name=name,
                role="配角",
                first_appearance_chapter=chapter.chapter_no,
                card={},
            )
            db.add(c)
        card = dict(c.card or {})
        if str(u.get("location", "")) not in _NO_CHANGE:
            card["位置"] = u["location"]
        if str(u.get("goal", "")) not in _NO_CHANGE:
            card["目标"] = u["goal"]
        if str(u.get("relationships", "")) not in _NO_CHANGE:
            card["关系"] = u["relationships"]
        if str(u.get("emotional_state", "")) not in _NO_CHANGE:
            card["情感"] = u["emotional_state"]
        c.card = card

    # 5. 章节定稿
    chapter.status = "已定稿"
