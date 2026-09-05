"""小说书架：列表 / 新建 / 详情 / 修改 / 删除 / 导出"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Chapter, Novel, Volume, utcnow
from app.schemas import ExportIn, NovelDetailOut, NovelIn, NovelOut, VolumeWithChapters

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _chapter_count(db: Session, novel_id: int) -> int:
    return db.query(Chapter).filter(Chapter.novel_id == novel_id).count()


@router.get("", response_model=list[NovelOut])
def list_novels(db: Session = Depends(get_db)):
    novels = db.query(Novel).order_by(Novel.updated_at.desc()).all()
    result = []
    for n in novels:
        out = NovelOut.model_validate(n)
        out.chapter_count = _chapter_count(db, n.id)
        result.append(out)
    return result


@router.post("", response_model=NovelOut)
def create_novel(body: NovelIn, db: Session = Depends(get_db)):
    novel = Novel(**body.model_dump())
    db.add(novel)
    db.flush()
    db.add(Volume(novel_id=novel.id, volume_no=1, title="第一卷"))  # 自动创建第一卷
    db.commit()
    db.refresh(novel)
    return NovelOut.model_validate(novel)


@router.get("/{novel_id}", response_model=NovelDetailOut)
def novel_detail(novel_id: int, db: Session = Depends(get_db)):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    volumes = (
        db.query(Volume)
        .filter(Volume.novel_id == novel_id)
        .order_by(Volume.volume_no)
        .all()
    )
    out = NovelOut.model_validate(novel)
    out.chapter_count = _chapter_count(db, novel_id)
    return NovelDetailOut(
        novel=out, volumes=[VolumeWithChapters.model_validate(v) for v in volumes]
    )


@router.put("/{novel_id}", response_model=NovelOut)
def update_novel(novel_id: int, body: NovelIn, db: Session = Depends(get_db)):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    for k, v in body.model_dump().items():
        setattr(novel, k, v)
    novel.updated_at = utcnow()
    db.commit()
    db.refresh(novel)
    out = NovelOut.model_validate(novel)
    out.chapter_count = _chapter_count(db, novel_id)
    return out


def _safe_filename(name: str) -> str:
    """剔除 Windows 文件名非法字符"""
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "export"


@router.post("/{novel_id}/export")
def export_novel(novel_id: int, body: ExportIn, db: Session = Depends(get_db)):
    """自由选择章节导出 txt：含书名/卷名/章标题，可选附带细纲（供 AI 漫剧分镜参考）"""
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    if not body.chapter_ids:
        raise HTTPException(status_code=400, detail="请选择要导出的章节")
    chapters = (
        db.query(Chapter)
        .filter(Chapter.novel_id == novel_id, Chapter.id.in_(body.chapter_ids))
        .order_by(Chapter.chapter_no)
        .all()
    )
    if not chapters:
        raise HTTPException(status_code=404, detail="所选章节不存在")
    volumes = {v.id: v for v in db.query(Volume).filter(Volume.novel_id == novel_id).all()}

    lines = [novel.title, ""]
    current_volume_id = None
    for ch in chapters:
        v = volumes.get(ch.volume_id)
        if v and v.id != current_volume_id:
            lines.append(f"【{v.title}】")
            lines.append("")
            current_volume_id = v.id
        lines.append(f"第{ch.chapter_no}章 {ch.title}")
        lines.append("")
        if body.include_outline and ch.detailed_outline.strip():
            lines.append("【细纲】")
            lines.append(ch.detailed_outline.strip())
            lines.append("")
        lines.append(ch.content.strip())
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    filename = f"{novel.title}_第{chapters[0].chapter_no}-{chapters[-1].chapter_no}章.txt"
    return Response(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(_safe_filename(filename))}",
        },
    )


@router.delete("/{novel_id}")
def delete_novel(novel_id: int, db: Session = Depends(get_db)):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    db.query(Chapter).filter(Chapter.novel_id == novel_id).delete()
    db.query(Volume).filter(Volume.novel_id == novel_id).delete()
    db.delete(novel)
    db.commit()
    return {"ok": True}
