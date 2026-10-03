from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane
from app.api.sku_caps import get_sku_cap_map
from app.services.fill_engine import build_fill_lines
router = APIRouter(prefix="/lanes", tags=["lanes"])

@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None: q = q.where(Lane.location_id == location_id)
    lanes = db.scalars(q).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]
    # Same truncation engine as the receipt and summary: the lane list shows
    # the effective fill and 同品合计已满 reason produced by the aggregate caps.
    caps = get_sku_cap_map(db, location_id) if location_id is not None else {}
    lines = {fl.lane_id: fl for fl in build_fill_lines(payload, sku_caps=caps)}
    out = []
    for l in lanes:
        fl = lines[l.id]
        out.append({"id": l.id, "location_id": l.location_id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                    "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit, "gap": fl.gap,
                    "fill_qty": fl.fill_qty, "status": fl.status, "reason": fl.reason,
                    "fill_pct": round(l.stock / l.capacity * 100, 1) if l.capacity else 0})
    return out
