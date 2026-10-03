from fastapi import APIRouter
from app.api import lanes, locations, refills, sales, sku_caps
api_router = APIRouter()

@api_router.get("/health")
def health():
    return {"status": "ok"}

api_router.include_router(locations.router)
api_router.include_router(lanes.router)
api_router.include_router(sku_caps.router)
api_router.include_router(sales.router)
api_router.include_router(refills.router)
