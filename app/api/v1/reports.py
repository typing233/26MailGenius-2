import csv
import io
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.database import get_db
from app.dependencies import CurrentUser, require_permissions
from app.models.campaign import Campaign
from app.models.report import CampaignReport
from app.models.tracking import TrackingEvent
from app.schemas.report import CampaignReportResponse, ExportRequest, ReportDashboardResponse

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard", response_model=ReportDashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.REPORT_READ),
):
    base = select(Campaign).where(
        Campaign.tenant_id == user.tenant_id,
        Campaign.deleted_at.is_(None),
    )
    total_campaigns = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0

    active = (await db.execute(
        select(func.count()).where(
            Campaign.tenant_id == user.tenant_id,
            Campaign.status == "sending",
            Campaign.deleted_at.is_(None),
        )
    )).scalar() or 0

    agg = await db.execute(
        select(
            func.coalesce(func.sum(Campaign.sent_count), 0),
            func.coalesce(func.sum(Campaign.opened_count), 0),
            func.coalesce(func.sum(Campaign.clicked_count), 0),
            func.coalesce(func.sum(Campaign.bounced_count), 0),
        ).where(
            Campaign.tenant_id == user.tenant_id,
            Campaign.deleted_at.is_(None),
        )
    )
    row = agg.one()
    total_sent = row[0]
    total_opened = row[1]
    total_clicked = row[2]
    total_bounced = row[3]

    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active,
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_clicked": total_clicked,
        "total_bounced": total_bounced,
        "overall_open_rate": round(total_opened / total_sent * 100, 2) if total_sent else 0,
        "overall_click_rate": round(total_clicked / total_sent * 100, 2) if total_sent else 0,
    }


@router.get("/campaigns/{campaign_id}/summary")
async def get_campaign_summary(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.REPORT_READ),
):
    stmt = select(CampaignReport).where(
        CampaignReport.campaign_id == uuid.UUID(campaign_id),
        CampaignReport.tenant_id == user.tenant_id,
    ).order_by(CampaignReport.generated_at.desc()).limit(1)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    if report:
        return CampaignReportResponse.model_validate(report)
    # Fallback to live stats
    campaign = await db.execute(
        select(Campaign).where(Campaign.id == uuid.UUID(campaign_id), Campaign.tenant_id == user.tenant_id)
    )
    c = campaign.scalar_one_or_none()
    if not c:
        from app.exceptions import AppException
        raise AppException(status_code=404, detail="Campaign not found")
    total = c.total_recipients or 1
    return {
        "campaign_id": c.id,
        "report_type": "live",
        "metrics": {
            "sent": c.sent_count, "opened": c.opened_count,
            "clicked": c.clicked_count, "bounced": c.bounced_count,
        },
        "funnel": {
            "delivery_rate": round((c.sent_count - c.bounced_count) / total * 100, 2),
            "open_rate": round(c.opened_count / total * 100, 2),
            "click_rate": round(c.clicked_count / total * 100, 2),
        },
    }


@router.get("/campaigns/{campaign_id}/timeline")
async def get_timeline(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.REPORT_READ),
):
    stmt = select(
        func.date_trunc("hour", TrackingEvent.occurred_at).label("hour"),
        TrackingEvent.event_type,
        func.count().label("count"),
    ).where(
        TrackingEvent.tenant_id == user.tenant_id,
        TrackingEvent.campaign_id == uuid.UUID(campaign_id),
    ).group_by("hour", TrackingEvent.event_type).order_by("hour")

    result = await db.execute(stmt)
    rows = result.all()
    timeline = [{"hour": str(r[0]), "event_type": r[1], "count": r[2]} for r in rows]
    return {"timeline": timeline}


@router.get("/campaigns/{campaign_id}/funnel")
async def get_funnel(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.REPORT_READ),
):
    campaign = (await db.execute(
        select(Campaign).where(Campaign.id == uuid.UUID(campaign_id), Campaign.tenant_id == user.tenant_id)
    )).scalar_one_or_none()
    if not campaign:
        from app.exceptions import AppException
        raise AppException(status_code=404, detail="Campaign not found")

    total = campaign.total_recipients or 1
    return {
        "funnel": [
            {"stage": "Sent", "count": campaign.sent_count, "pct": 100},
            {"stage": "Delivered", "count": campaign.sent_count - campaign.bounced_count, "pct": round((campaign.sent_count - campaign.bounced_count) / total * 100, 1)},
            {"stage": "Opened", "count": campaign.opened_count, "pct": round(campaign.opened_count / total * 100, 1)},
            {"stage": "Clicked", "count": campaign.clicked_count, "pct": round(campaign.clicked_count / total * 100, 1)},
        ]
    }


@router.post("/export")
async def export_report(
    data: ExportRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = require_permissions(Permission.REPORT_READ),
):
    base = select(TrackingEvent).where(TrackingEvent.tenant_id == user.tenant_id)
    if data.campaign_id:
        base = base.where(TrackingEvent.campaign_id == data.campaign_id)
    if data.date_from:
        base = base.where(TrackingEvent.occurred_at >= data.date_from)
    if data.date_to:
        base = base.where(TrackingEvent.occurred_at <= data.date_to)

    result = await db.execute(base.order_by(TrackingEvent.occurred_at.desc()).limit(10000))
    events = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["event_type", "campaign_id", "subscriber_id", "link_url", "occurred_at", "is_first"])
    for e in events:
        writer.writerow([e.event_type, str(e.campaign_id), str(e.subscriber_id), e.link_url or "", str(e.occurred_at), e.is_first])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=report.csv"},
    )
