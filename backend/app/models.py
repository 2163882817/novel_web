from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApiConfig(Base):
    """单行表：用户自己的 OpenAI 兼容 API 配置"""
    __tablename__ = "api_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_url: Mapped[str] = mapped_column(String(500), default="")
    api_key_enc: Mapped[str] = mapped_column(Text, default="")  # Fernet 加密
    model_name: Mapped[str] = mapped_column(String(200), default="")
    context_window: Mapped[int] = mapped_column(Integer, default=64000)
    temperature: Mapped[float] = mapped_column(Float, default=0.8)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Novel(Base):
    """小说（书架条目）"""
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str] = mapped_column(String(50), default="")
    style: Mapped[str] = mapped_column(String(200), default="")
    protagonist: Mapped[str] = mapped_column(String(100), default="")
    world_setting: Mapped[str] = mapped_column(Text, default="")
    synopsis: Mapped[str] = mapped_column(Text, default="")
    story_bible_text: Mapped[str] = mapped_column(Text, default="")  # 导入的故事圣经原文（设定铁律）
    book_outline_text: Mapped[str] = mapped_column(Text, default="")  # 导入的全书总纲（硬性红线）
    writing_restrictions_text: Mapped[str] = mapped_column(Text, default="")  # AI 写作限制词/去模板化规则原文
    story_bible: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 预留
    book_outline: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 预留
    target_word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="连载中")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Volume(Base):
    """卷"""
    __tablename__ = "volumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), index=True)
    volume_no: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200), default="")
    outline: Mapped[str] = mapped_column(Text, default="")  # 卷大纲（细纲师规划依据）
    summary: Mapped[str] = mapped_column(Text, default="")  # 卷摘要（卷完结后生成）
    status: Mapped[str] = mapped_column(String(20), default="连载中")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chapters: Mapped[list["Chapter"]] = relationship(order_by="Chapter.chapter_no")


class Chapter(Base):
    """章节"""
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), index=True)
    volume_id: Mapped[int] = mapped_column(ForeignKey("volumes.id"), index=True)
    chapter_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300), default="")
    detailed_outline: Mapped[str] = mapped_column(Text, default="")  # 已确认细纲（文本版）
    content: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="草稿")  # 草稿 → 定稿(更新记忆)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ChapterSummary(Base):
    """章摘要（每章定稿后由总结师生成）"""
    __tablename__ = "chapter_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    key_events: Mapped[list] = mapped_column(JSON, default=list)
    outline_progress: Mapped[str] = mapped_column(Text, default="")
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Character(Base):
    """人物卡：角色设定与当前状态（跨章连贯的关键）"""
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="配角")  # 主角/反派/配角
    card: Mapped[dict] = mapped_column(JSON, default=dict)  # 外貌/性格/目标/关系/位置/情感
    raw_profile: Mapped[str] = mapped_column(Text, default="")  # 导入的人物卡原文（人设约束）
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Foreshadowing(Base):
    """伏笔库：每条伏笔一个坑，状态流转 待回收 → 已回收 / 废弃"""
    __tablename__ = "foreshadowings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="待回收")
    planted_chapter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_chapter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class GenerationLog(Base):
    """生成日志：成本统计的基础（token 为粗估）"""
    __tablename__ = "generation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    novel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_type: Mapped[str] = mapped_column(String(50), default="writer")  # planner/writer/checker/summarizer
    model_name: Mapped[str] = mapped_column(String(200), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="成功")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
