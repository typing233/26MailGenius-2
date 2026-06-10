from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.channels import router as channels_router
from app.api.v1.dead_letter import router as dead_letter_router
from app.api.v1.embed import router as embed_router
from app.api.v1.import_export import router as import_export_router
from app.api.v1.mailing_lists import router as lists_router
from app.api.v1.reports import router as reports_router
from app.api.v1.segments import router as segments_router
from app.api.v1.send_queue import router as send_queue_router
from app.api.v1.subscribers import router as subscribers_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.suppression import router as suppression_router
from app.api.v1.templates import router as templates_router
from app.api.v1.tracking import router as tracking_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(subscribers_router)
router.include_router(lists_router)
router.include_router(import_export_router)
router.include_router(subscription_router)
router.include_router(embed_router)
router.include_router(send_queue_router)
router.include_router(templates_router)
router.include_router(campaigns_router)
router.include_router(segments_router)
router.include_router(channels_router)
router.include_router(tracking_router)
router.include_router(reports_router)
router.include_router(dead_letter_router)
router.include_router(suppression_router)
