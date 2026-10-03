from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Location, SkuFillCap
router = APIRouter(prefix="/sku-caps", tags=["sku-caps"])


class CapIn(BaseModel):
    location_id: int
    sku_name: str = Field(min_length=1)
    cap_qty: int


def _load_map(db: Session, location_id: int) -> dict[str, int]:
    rows = db.scalars(select(SkuFillCap).where(SkuFillCap.location_id == location_id)).all()
    return {r.sku_name: r.cap_qty for r in rows}


def get_sku_cap_map(db: Session, location_id: int) -> dict[str, int]:
    return _load_map(db, location_id)


@router.get("")
def list_caps(location_id: int, db: Session = Depends(get_db)):
    return [{"id": r.id, "location_id": r.location_id, "sku_name": r.sku_name, "cap_qty": r.cap_qty}
            for r in db.scalars(
                select(SkuFillCap).where(SkuFillCap.location_id == location_id)
                .order_by(SkuFillCap.sku_name)).all()]


@router.put("")
def upsert_cap(body: CapIn, db: Session = Depends(get_db)):
    # cap <= 0 is rejected before any config or document mutation.
    if body.cap_qty <= 0:
        raise HTTPException(400, "同品合计补量上限必须为正整数")
    sku_name = body.sku_name.strip()
    if not sku_name:
        raise HTTPException(400, "商品名不能为空")
    if not db.get(Location, body.location_id):
        raise HTTPException(404, "点位不存在")
    row = db.scalars(select(SkuFillCap).where(
        SkuFillCap.location_id == body.location_id,
        SkuFillCap.sku_name == sku_name)).first()
    if row:
        row.cap_qty = body.cap_qty
    else:
        row = SkuFillCap(location_id=body.location_id, sku_name=sku_name, cap_qty=body.cap_qty)
        db.add(row)
    db.commit(); db.refresh(row)
    return {"id": row.id, "location_id": row.location_id, "sku_name": row.sku_name, "cap_qty": row.cap_qty}


@router.delete("")
def delete_cap(location_id: int, sku_name: str, db: Session = Depends(get_db)):
    row = db.scalars(select(SkuFillCap).where(
        SkuFillCap.location_id == location_id,
        SkuFillCap.sku_name == sku_name.strip())).first()
    if row:
        db.delete(row); db.commit()
    return {"ok": True}
