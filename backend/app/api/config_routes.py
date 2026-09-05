"""API 配置：保存 / 读取 / 测试连接"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import llm_gateway
from app.crypto import decrypt, encrypt
from app.database import SessionLocal
from app.models import ApiConfig
from app.schemas import ApiConfigIn, ApiConfigOut

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _to_out(row: ApiConfig) -> ApiConfigOut:
    key = decrypt(row.api_key_enc)
    return ApiConfigOut(
        base_url=row.base_url,
        model_name=row.model_name,
        context_window=row.context_window,
        temperature=row.temperature,
        has_key=bool(key),
        key_tail=key[-4:] if key else "",
    )


@router.get("", response_model=ApiConfigOut)
def get_config(db: Session = Depends(get_db)):
    row = db.query(ApiConfig).order_by(ApiConfig.id).first()
    if not row:
        return ApiConfigOut(
            base_url="", model_name="", context_window=64000, temperature=0.8, has_key=False
        )
    return _to_out(row)


@router.put("", response_model=ApiConfigOut)
def save_config(body: ApiConfigIn, db: Session = Depends(get_db)):
    row = db.query(ApiConfig).order_by(ApiConfig.id).first()
    if not row:
        row = ApiConfig()
        db.add(row)
    row.base_url = body.base_url.strip()
    if body.api_key.strip():  # 留空 = 保留原 Key
        row.api_key_enc = encrypt(body.api_key.strip())
    row.model_name = body.model_name.strip()
    row.context_window = body.context_window
    row.temperature = body.temperature
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/test")
async def test_connection(db: Session = Depends(get_db)):
    cfg = llm_gateway.get_config()
    if not cfg:
        raise HTTPException(
            status_code=400, detail="请先保存完整的 API 配置（base_url / API Key / 模型名）"
        )
    return await llm_gateway.test_connection(cfg)
