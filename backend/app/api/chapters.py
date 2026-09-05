"""章节：保存 / 修改 / 删除（写作接口在 write_routes）"""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Chapter, Novel, Volume, utcnow
from app.schemas import ChapterCreateIn, ChapterOut, ChapterUpdateIn

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _wc(text: str) -> int:
    return len(re.sub(r"\s", "", text))


@router.post("", response_model=ChapterOut)
def create_chapter(body: ChapterCreateIn, db: Session = Depends(get_db)):
    novel = db.get(Novel, body.novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    # 优先写入「连载中」的卷（导入大纲后存在多个「未开始」的卷）
    volume = (
        db.query(Volume)
        .filter(Volume.novel_id == novel.id, Volume.status == "连载中")
        .order_by(Volume.volume_no.desc())
        .first()
    )
    if not volume:
        volume = (
            db.query(Volume)
            .filter(Volume.novel_id == novel.id)
            .order_by(Volume.volume_no.desc())
            .first()
        )
    if not volume:
        raise HTTPException(status_code=500, detail="小说缺少卷，请删除后重建")
    last = (
        db.query(Chapter)
        .filter(Chapter.novel_id == novel.id)
        .order_by(Chapter.chapter_no.desc())
        .first()
    )
    chapter_no = (last.chapter_no + 1) if last else 1
    ch = Chapter(
        novel_id=novel.id,
        volume_id=volume.id,
        chapter_no=chapter_no,
        title=body.title or f"第{chapter_no}章",
        content=body.content,
        detailed_outline=body.detailed_outline,
        word_count=_wc(body.content),
    )
    novel.updated_at = utcnow()
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


@router.put("/{chapter_id}", response_model=ChapterOut)
def update_chapter(chapter_id: int, body: ChapterUpdateIn, db: Session = Depends(get_db)):
    ch = db.get(Chapter, chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")
    if body.title:
        ch.title = body.title
    ch.content = body.content
    ch.word_count = _wc(body.content)
    if body.detailed_outline is not None:
        ch.detailed_outline = body.detailed_outline
    novel = db.get(Novel, ch.novel_id)
    if novel:
        novel.updated_at = utcnow()
    db.commit()
    db.refresh(ch)
    return ch


@router.delete("/{chapter_id}")
def delete_chapter(chapter_id: int, db: Session = Depends(get_db)):
    ch = db.get(Chapter, chapter_id)
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")
    db.delete(ch)
    db.commit()
    return {"ok": True}
