from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiConfigIn(BaseModel):
    base_url: str
    model_name: str
    api_key: str = ""  # 留空 = 保留已保存的 Key
    context_window: int = 64000
    temperature: float = Field(default=0.8, ge=0, le=2)


class ApiConfigOut(BaseModel):
    base_url: str
    model_name: str
    context_window: int
    temperature: float
    has_key: bool
    key_tail: str = ""  # 已保存 Key 的尾号，仅用于回显


class WriteRequest(BaseModel):
    """单章写作请求；novel_id 提供时自动从小说资料与记忆库补全上下文"""
    novel_id: int | None = None
    title: str = ""
    genre: str = ""
    style: str = ""
    protagonist: str = ""
    world_setting: str = ""
    synopsis: str = ""
    outline: str = ""
    previous_text: str = ""
    chapter_no: int = 0  # 0 = 自动取下一章号（novel_id 模式）；手动指定则重写该章
    max_tokens: int = 4096
    writing_restrictions: str = ""


class VariantOut(BaseModel):
    label: Literal["A", "B", "C"]
    content: str
    word_count: int


class VariantsOut(BaseModel):
    variants: list[VariantOut]
    duration_ms: int


class NovelIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    genre: str = ""
    style: str = ""
    protagonist: str = ""
    world_setting: str = ""
    synopsis: str = ""
    target_word_count: int = 0


class NovelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    genre: str
    style: str
    protagonist: str
    world_setting: str
    synopsis: str
    target_word_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    chapter_count: int = 0


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    volume_id: int
    chapter_no: int
    title: str
    content: str
    detailed_outline: str
    word_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class VolumeWithChapters(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    volume_no: int
    title: str
    status: str
    chapters: list[ChapterOut]


class NovelDetailOut(BaseModel):
    novel: NovelOut
    volumes: list[VolumeWithChapters]


class ChapterCreateIn(BaseModel):
    novel_id: int
    title: str = ""
    content: str
    detailed_outline: str = ""


class ChapterUpdateIn(BaseModel):
    title: str = ""
    content: str = ""
    detailed_outline: str | None = None  # None = 不修改


# ---------- 记忆系统 ----------

class Scene(BaseModel):
    scene_no: int = 0
    location: str = ""
    participants: list[str] = []
    events: str = ""
    goal: str = ""


class PlannerOut(BaseModel):
    """细纲师输出"""
    chapter_title: str = ""
    scenes: list[Scene] = []
    foreshadowings_planted: list[dict] = []
    foreshadowings_resolved: list[str] = []
    hook: str = ""
    word_target: int = 2500


class CheckIssue(BaseModel):
    severity: str = "medium"  # high / medium / low
    type: str = ""
    location: str = ""
    description: str = ""
    suggestion: str = ""


class CheckerOut(BaseModel):
    """校对输出"""
    issues: list[CheckIssue] = []
    verdict: str = "pass"  # pass / need_fix


class CharacterUpdate(BaseModel):
    name: str = ""
    location: str = ""
    goal: str = ""
    relationships: str = ""
    emotional_state: str = ""


class SummarizerOut(BaseModel):
    """总结师输出"""
    summary: str = ""
    key_events: list[str] = []
    character_state_updates: list[CharacterUpdate] = []
    foreshadowings_planted: list[dict] = []
    foreshadowings_resolved: list[str] = []
    outline_progress: str = ""


class CharacterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = "配角"
    card: dict = {}


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    name: str
    role: str
    card: dict
    first_appearance_chapter: int | None


class ForeshadowingIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: str = "待回收"


class ForeshadowingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    title: str
    description: str
    status: str
    planted_chapter_id: int | None
    resolved_chapter_id: int | None
    updated_at: datetime


class VolumeOut(BaseModel):
    id: int
    volume_no: int
    title: str
    outline: str
    summary: str
    status: str
    chapter_count: int = 0


class VolumeCreateIn(BaseModel):
    title: str = ""
    outline: str = ""


class VolumeUpdateIn(BaseModel):
    title: str | None = None      # None = 不修改
    outline: str | None = None
    status: str | None = None


class VolumeOutlineOut(BaseModel):
    outline: str = ""
    volume_title: str = ""


class VolumeSummaryOut(BaseModel):
    summary: str = ""
    key_developments: list[str] = []
    unresolved: list[str] = []


class MemoryOut(BaseModel):
    volumes: list[VolumeOut] = []
    characters: list[CharacterOut]
    foreshadowings: list[ForeshadowingOut]
    summaries: list[dict] = []  # [{chapter_no, chapter_title, summary, key_events, outline_progress, created_at}]
    writing_restrictions: dict = {}


class ReviseIn(BaseModel):
    """修稿请求：携带用户勾选的校对问题"""
    issues: list[dict] = []


class ExportIn(BaseModel):
    """导出请求：自由勾选章节"""
    chapter_ids: list[int] = []
    include_outline: bool = False


class ImportIn(BaseModel):
    """设定导入：kind = bible / outline / characters / restrictions"""
    kind: Literal["bible", "outline", "characters", "restrictions"]
    text: str = Field(min_length=1, max_length=100_000)
    mode: Literal["replace", "append"] = "replace"


class TitleIn(BaseModel):
    """标题生成请求：正文或细纲至少提供一个"""
    novel_id: int | None = None
    content: str = ""
    outline: str = ""
    chapter_no: int = 1
    count: int = 5


class TitlesOut(BaseModel):
    titles: list[str] = []
