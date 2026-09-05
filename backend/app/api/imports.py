"""设定导入：故事圣经 / 人物卡 / 故事大纲（markdown 文本）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import importers
from app.database import SessionLocal
from app.models import Character, Novel, Volume
from app.schemas import ImportIn

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.delete("/novels/{novel_id}/writing-restrictions")
def clear_writing_restrictions(novel_id: int, db: Session = Depends(get_db)):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    novel.writing_restrictions_text = ""
    db.commit()
    return {"ok": True, "message": "AI 写作限制词文档已清空"}


@router.post("/novels/{novel_id}/import")
def import_doc(novel_id: int, body: ImportIn, db: Session = Depends(get_db)):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="导入内容为空")
    kind = body.kind

    if kind == "bible":
        r = importers.parse_bible(text)
        if body.mode == "replace" or not novel.story_bible_text:
            novel.story_bible_text = text
        else:
            novel.story_bible_text += "\n\n" + text
        nf = r["novel_fields"]
        updated = []
        if body.mode == "replace" or not novel.title:
            if nf.get("title"):
                novel.title = nf["title"]
                updated.append("书名")
        if body.mode == "replace" or not novel.genre:
            if nf.get("genre"):
                novel.genre = nf["genre"]
                updated.append("题材")
        if body.mode == "replace" or not novel.style:
            if nf.get("style"):
                novel.style = nf["style"]
                updated.append("风格")
        if body.mode == "replace" or not novel.synopsis:
            if nf.get("synopsis"):
                novel.synopsis = nf["synopsis"]
                updated.append("简介")
        if nf.get("target_word_count"):
            novel.target_word_count = nf["target_word_count"]
            updated.append("目标字数")
        db.commit()
        return {"ok": True, "message": f"故事圣经已导入（{len(text)} 字），同步字段：{('、'.join(updated)) if updated else '无'}", "imported": []}

    if kind == "outline":
        r = importers.parse_outline(text)
        if not r["volumes"]:
            raise HTTPException(status_code=400, detail="未解析出分卷，请确认「### 卷X《卷名》(起-止 章)」格式")
        if body.mode == "replace" or not novel.book_outline_text:
            novel.book_outline_text = r["book_rules"]
        else:
            novel.book_outline_text += "\n\n" + r["book_rules"]
        if r["synopsis"] and (body.mode == "replace" or not novel.synopsis):
            novel.synopsis = r["synopsis"]
        vol_msgs = []
        for v in r["volumes"]:
            existing = (
                db.query(Volume)
                .filter(Volume.novel_id == novel_id, Volume.volume_no == v["volume_no"])
                .first()
            )
            if existing:
                existing.outline = v["outline"] if body.mode == "replace" else existing.outline + "\n\n" + v["outline"]
                if body.mode == "replace" or existing.title.startswith("第"):
                    existing.title = v["title"]
                vol_msgs.append(f"第{v['volume_no']}卷已更新")
            else:
                db.add(Volume(
                    novel_id=novel_id,
                    volume_no=v["volume_no"],
                    title=v["title"],
                    outline=v["outline"],
                    status="连载中" if v["volume_no"] == 1 else "未开始",
                ))
                vol_msgs.append(f"第{v['volume_no']}卷已创建")
        db.commit()
        return {"ok": True, "message": "故事大纲已导入：" + "；".join(vol_msgs), "imported": [v["title"] for v in r["volumes"]]}

    if kind == "characters":
        chars = importers.parse_characters(text)
        if not chars:
            raise HTTPException(status_code=400, detail="未解析出人物卡，请确认每张卡以「## N. 角色名」开头")
        if body.mode == "replace":
            db.query(Character).filter(Character.novel_id == novel_id).delete()
        names = []
        for c in chars:
            existing = (
                db.query(Character)
                .filter(Character.novel_id == novel_id, Character.name == c["name"])
                .first()
            )
            if existing:
                existing.role = c["role"]
                existing.card = c["card"]
                existing.raw_profile = c["raw_profile"]
            else:
                db.add(Character(
                    novel_id=novel_id,
                    name=c["name"],
                    role=c["role"],
                    card=c["card"],
                    raw_profile=c["raw_profile"],
                ))
            names.append(c["name"])
        db.commit()
        head = "、".join(names[:8]) + ("…" if len(names) > 8 else "")
        return {"ok": True, "message": f"已导入 {len(names)} 张人物卡：{head}", "imported": names}

    if kind == "restrictions":
        if body.mode == "replace" or not novel.writing_restrictions_text:
            novel.writing_restrictions_text = text
        else:
            novel.writing_restrictions_text += "\n\n" + text
        db.commit()
        return {
            "ok": True,
            "kind": kind,
            "length": len(novel.writing_restrictions_text),
            "message": f"AI 写作限制词文档已{('覆盖' if body.mode == 'replace' else '追加')}（当前 {len(novel.writing_restrictions_text)} 字）",
        }

    raise HTTPException(status_code=400, detail="kind 仅支持 bible / outline / characters / restrictions")
