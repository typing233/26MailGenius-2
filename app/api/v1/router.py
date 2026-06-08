from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.embed import router as embed_router
from app.api.v1.import_export import router as import_export_router
from app.api.v1.mailing_lists import router as lists_router
from app.api.v1.send_queue import router as send_queue_router
from app.api.v1.subscribers import router as subscribers_router
from app.api.v1.subscription import router as subscription_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(subscribers_router)
router.include_router(lists_router)
router.include_router(import_export_router)
router.include_router(subscription_router)
router.include_router(embed_router)
router.include_router(send_queue_router)
