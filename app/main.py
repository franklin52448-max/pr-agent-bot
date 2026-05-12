from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from contextlib import suppress

from fastapi import FastAPI, HTTPException, Query

from .campaigns import STORE, CampaignRecord
from .config import settings
from .models import (
    CampaignStatusResponse,
    JournalistMatch,
    MatchPreviewRequest,
    MatchPreviewResponse,
    RegisterRequest,
    RegisterResponse,
    PitchStatus,
    X402Quote,
)
from .outreach import build_followup_text, build_pitch_text, build_sender, followup_subject, pitch_subject
from .payments import quote_usdc

app = FastAPI(title=settings.app_name, version=settings.app_version)
_background_tasks: list[asyncio.Task] = []


def _quote_model(pitch_count: int) -> X402Quote:
    quote = quote_usdc(pitch_count)
    return X402Quote(**quote)


def _match_model(match: dict) -> JournalistMatch:
    return JournalistMatch(
        journalist_id=str(match["journalist_id"]),
        name=str(match["name"]),
        email=str(match["email"]),
        outlet=str(match["outlet"]),
        beat=str(match["beat"]),
        region=str(match["region"]),
        score=float(match["score"]),
        rationale=list(match["rationale"]),
        estimated_cost_usdc=f"{settings.price_per_pitch_usdc:.2f}",
    )


def _pitch_model(pitch) -> PitchStatus:
    return PitchStatus(
        journalist_id=pitch.journalist_id,
        name=pitch.name,
        email=pitch.email,
        outlet=pitch.outlet,
        beat=pitch.beat,
        score=pitch.score,
        rationale=list(pitch.rationale),
        status=pitch.status,
        sent_at=pitch.sent_at,
        follow_up_sent_at=pitch.follow_up_sent_at,
        provider=pitch.provider,
        provider_message_id=pitch.provider_message_id,
        error=pitch.error,
    )


async def _send_initial_campaign(campaign: CampaignRecord) -> None:
    sender = build_sender(settings)
    now = datetime.now(timezone.utc)
    for pitch in campaign.pitches:
        subject = pitch_subject(campaign.product, pitch.outlet)
        body = build_pitch_text(campaign.product, pitch.name, pitch.rationale, campaign.x402)
        try:
            delivery = await sender.send(to_email=pitch.email, subject=subject, text=body)
            STORE.record_delivery(campaign.campaign_id, pitch.journalist_id, provider=delivery.provider, message_id=delivery.message_id, sent_at=now)
        except Exception as exc:  # pragma: no cover - surfaced in response/status
            STORE.record_failure(campaign.campaign_id, pitch.journalist_id, str(exc))

    campaign = STORE.get_campaign(campaign.campaign_id)
    if campaign is not None:
        campaign.status = "awaiting_response"
        campaign.updated_at = datetime.now(timezone.utc)


async def _send_followups(campaign: CampaignRecord) -> None:
    sender = build_sender(settings)
    now = datetime.now(timezone.utc)
    for pitch in campaign.pitches:
        if pitch.sent_at is None or pitch.follow_up_sent_at is not None:
            continue
        if campaign.response_received_at is not None:
            continue
        subject = followup_subject(campaign.product, pitch.outlet)
        body = build_followup_text(campaign.product, pitch.name, pitch.rationale)
        try:
            delivery = await sender.send(to_email=pitch.email, subject=subject, text=body)
            STORE.mark_followup_sent(campaign.campaign_id, pitch.journalist_id, provider=delivery.provider, message_id=delivery.message_id, sent_at=now)
        except Exception as exc:  # pragma: no cover - surfaced in response/status
            STORE.record_failure(campaign.campaign_id, pitch.journalist_id, str(exc))


async def weekly_update_worker() -> None:
    while True:
        await asyncio.sleep(settings.weekly_update_poll_seconds)
        now = datetime.now(timezone.utc)
        STORE.maybe_run_weekly_update(now)


async def followup_worker() -> None:
    while True:
        await asyncio.sleep(settings.follow_up_poll_seconds)
        now = datetime.now(timezone.utc)
        for campaign in STORE.due_followups(now, settings.follow_up_after_days):
            await _send_followups(campaign)


@app.on_event("startup")
async def startup_event() -> None:
    STORE.ensure_seeded()
    _background_tasks.append(asyncio.create_task(weekly_update_worker()))
    _background_tasks.append(asyncio.create_task(followup_worker()))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for task in _background_tasks:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    _background_tasks.clear()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.post("/match-preview", response_model=MatchPreviewResponse)
async def match_preview(request: MatchPreviewRequest) -> MatchPreviewResponse:
    STORE.ensure_seeded()
    matches = STORE.preview_matches(request.product, request.max_journalists)
    quote = _quote_model(len(matches))
    return MatchPreviewResponse(
        total_considered=len(STORE.journalists),
        pitch_count=len(matches),
        price_per_pitch_usdc=f"{settings.price_per_pitch_usdc:.2f}",
        total_usdc=quote.total_usdc,
        x402=quote,
        matches=[_match_model(match) for match in matches],
    )


@app.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest) -> RegisterResponse:
    STORE.ensure_seeded()
    dry_run = request.dry_run if request.dry_run is not None else settings.dry_run_default
    matches = STORE.preview_matches(request.product, request.max_journalists)
    campaign = STORE.create_campaign(request.product, dry_run, matches)

    if not dry_run:
        try:
            await _send_initial_campaign(campaign)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        campaign = STORE.get_campaign(campaign.campaign_id) or campaign
    else:
        campaign.status = "preview"

    sent_count = sum(1 for pitch in campaign.pitches if pitch.status == "sent")
    return RegisterResponse(
        campaign_id=campaign.campaign_id,
        dry_run=dry_run,
        status=campaign.status,
        pitch_count=campaign.pitch_count,
        sent_count=sent_count,
        provider=(campaign.pitches[0].provider if campaign.pitches and campaign.pitches[0].provider else None),
        price_per_pitch_usdc=f"{settings.price_per_pitch_usdc:.2f}",
        total_usdc=campaign.x402["total_usdc"],
        x402=X402Quote(**campaign.x402),
        matches=[_match_model(match) for match in matches],
    )


@app.get("/status", response_model=CampaignStatusResponse)
async def status(campaign_id: str = Query(..., min_length=6)) -> CampaignStatusResponse:
    payload = STORE.to_status(campaign_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    return CampaignStatusResponse(
        campaign_id=payload["campaign_id"],
        status=payload["status"],
        dry_run=payload["dry_run"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        product=payload["product"],
        pitch_count=payload["pitch_count"],
        sent_count=payload["sent_count"],
        response_count=payload["response_count"],
        follow_up_sent_count=payload["follow_up_sent_count"],
        last_response_at=payload["last_response_at"],
        last_weekly_update_at=payload["last_weekly_update_at"],
        price_per_pitch_usdc=f"{settings.price_per_pitch_usdc:.2f}",
        total_usdc=payload["x402"]["total_usdc"],
        x402=X402Quote(**payload["x402"]),
        pitches=[_pitch_model(pitch) for pitch in payload["pitches"]],
    )
