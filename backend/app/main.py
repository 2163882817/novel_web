"""AI 网文写作台 —— FastAPI 入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import chapters, config_routes, imports, memory_routes, novels, write_routes
from app.database import Base, engine


def _migrate():
    """轻量迁移：为旧表补列（SQLite 的 create_all 不会修改已有表）"""
    with engine.begin() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(generation_logs)"))]
        if "novel_id" not in cols:
            conn.execute(text("ALTER TABLE generation_logs ADD COLUMN novel_id INTEGER"))
        if "chapter_id" not in cols:
            conn.execute(text("ALTER TABLE generation_logs ADD COLUMN chapter_id INTEGER"))
        if "prompt_tokens" not in cols:
            conn.execute(text("ALTER TABLE generation_logs ADD COLUMN prompt_tokens INTEGER DEFAULT 0"))
        for table, col, ddl in [
            ("novels", "story_bible_text", "ALTER TABLE novels ADD COLUMN story_bible_text TEXT DEFAULT ''"),
            ("novels", "book_outline_text", "ALTER TABLE novels ADD COLUMN book_outline_text TEXT DEFAULT ''"),
            ("novels", "writing_restrictions_text", "ALTER TABLE novels ADD COLUMN writing_restrictions_text TEXT DEFAULT ''"),
            ("characters", "raw_profile", "ALTER TABLE characters ADD COLUMN raw_profile TEXT DEFAULT ''"),
        ]:
            tcols = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))]
            if col not in tcols:
                conn.execute(text(ddl))


Base.metadata.create_all(bind=engine)
_migrate()

app = FastAPI(title="AI 网文写作台", version="0.3.0")

# 单机使用，放开跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_routes.router, prefix="/api/config", tags=["API 配置"])
app.include_router(novels.router, prefix="/api/novels", tags=["书架"])
app.include_router(chapters.router, prefix="/api/chapters", tags=["章节"])
app.include_router(memory_routes.router, prefix="/api", tags=["记忆系统"])
app.include_router(imports.router, prefix="/api", tags=["设定导入"])
app.include_router(write_routes.router, prefix="/api", tags=["写作"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
