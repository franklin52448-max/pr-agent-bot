from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from .models import ProductProfile
from .payments import quote_usdc


@dataclass
class JournalistRecord:
    journalist_id: str
    name: str
    email: str
    outlet: str
    beat: str
    region: str
    tags: list[str]
    seniority: str
    freshness_score: float
    last_updated_at: datetime


@dataclass
class PitchRecord:
    journalist_id: str
    name: str
    email: str
    outlet: str
    beat: str
    region: str
    score: float
    rationale: list[str]
    status: str = "queued"
    sent_at: datetime | None = None
    follow_up_sent_at: datetime | None = None
    provider: str | None = None
    provider_message_id: str | None = None
    error: str | None = None


@dataclass
class CampaignRecord:
    campaign_id: str
    product: ProductProfile
    dry_run: bool
    created_at: datetime
    updated_at: datetime
    status: str
    pitch_count: int
    pitches: list[PitchRecord] = field(default_factory=list)
    response_count: int = 0
    response_received_at: datetime | None = None
    follow_up_sent_count: int = 0
    last_weekly_update_at: datetime | None = None
    x402: dict[str, Any] = field(default_factory=dict)

    def to_status_payload(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "status": self.status,
            "dry_run": self.dry_run,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "product": self.product,
            "pitch_count": self.pitch_count,
            "sent_count": sum(1 for pitch in self.pitches if pitch.status in {"sent", "follow_up_sent"}),
            "response_count": self.response_count,
            "follow_up_sent_count": self.follow_up_sent_count,
            "last_response_at": self.response_received_at,
            "last_weekly_update_at": self.last_weekly_update_at,
            "x402": self.x402,
            "pitches": self.pitches,
        }


class CampaignStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.journalists: list[JournalistRecord] = []
        self.campaigns: dict[str, CampaignRecord] = {}
        self.last_weekly_update_at = datetime.now(timezone.utc)
        self._seeded = False

    def ensure_seeded(self) -> None:
        with self._lock:
            if self._seeded:
                return
            from .seed import generate_journalist_seed

            self.journalists = generate_journalist_seed()
            self._seeded = True

    def preview_matches(self, product: ProductProfile, limit: int) -> list[dict[str, Any]]:
        from .scoring import rank_journalists

        self.ensure_seeded()
        return rank_journalists(product, self.journalists, limit)

    def create_campaign(self, product: ProductProfile, dry_run: bool, matches: list[dict[str, Any]]) -> CampaignRecord:
        now = datetime.now(timezone.utc)
        campaign_id = uuid4().hex[:12]
        pitches = [
            PitchRecord(
                journalist_id=str(match["journalist_id"]),
                name=str(match["name"]),
                email=str(match["email"]),
                outlet=str(match["outlet"]),
                beat=str(match["beat"]),
                region=str(match["region"]),
                score=float(match["score"]),
                rationale=list(match["rationale"]),
                status="dry_run" if dry_run else "queued",
            )
            for match in matches
        ]
        campaign = CampaignRecord(
            campaign_id=campaign_id,
            product=product,
            dry_run=dry_run,
            created_at=now,
            updated_at=now,
            status="preview" if dry_run else "awaiting_send",
            pitch_count=len(matches),
            pitches=pitches,
            x402=quote_usdc(len(matches)),
        )
        with self._lock:
            self.campaigns[campaign_id] = campaign
        return campaign

    def get_campaign(self, campaign_id: str) -> CampaignRecord | None:
        with self._lock:
            return self.campaigns.get(campaign_id)

    def list_campaigns(self) -> list[CampaignRecord]:
        with self._lock:
            return list(self.campaigns.values())

    def record_delivery(self, campaign_id: str, journalist_id: str, *, provider: str, message_id: str, sent_at: datetime, follow_up: bool = False) -> None:
        with self._lock:
            campaign = self.campaigns[campaign_id]
            for pitch in campaign.pitches:
                if pitch.journalist_id == journalist_id:
                    pitch.provider = provider
                    pitch.provider_message_id = message_id
                    pitch.sent_at = sent_at if not follow_up else pitch.sent_at or sent_at
                    pitch.follow_up_sent_at = sent_at if follow_up else pitch.follow_up_sent_at
                    pitch.status = "follow_up_sent" if follow_up else "sent"
                    break
            campaign.updated_at = sent_at
            campaign.status = "awaiting_response"

    def record_failure(self, campaign_id: str, journalist_id: str, error: str) -> None:
        with self._lock:
            campaign = self.campaigns[campaign_id]
            for pitch in campaign.pitches:
                if pitch.journalist_id == journalist_id:
                    pitch.status = "failed"
                    pitch.error = error
                    break
            campaign.updated_at = datetime.now(timezone.utc)

    def record_response(self, campaign_id: str, journalist_email: str) -> bool:
        now = datetime.now(timezone.utc)
        with self._lock:
            campaign = self.campaigns.get(campaign_id)
            if campaign is None:
                return False
            found = False
            for pitch in campaign.pitches:
                if pitch.email == journalist_email:
                    found = True
                    break
            if not found:
                return False
            campaign.response_count += 1
            campaign.response_received_at = now
            campaign.updated_at = now
            campaign.status = "responded"
            return True

    def due_followups(self, now: datetime, after_days: int) -> list[CampaignRecord]:
        threshold = now - timedelta(days=after_days)
        with self._lock:
            due: list[CampaignRecord] = []
            for campaign in self.campaigns.values():
                if campaign.dry_run or campaign.status == "responded":
                    continue
                if campaign.response_received_at is not None:
                    continue
                if campaign.follow_up_sent_count:
                    continue
                sent_pitches = [pitch for pitch in campaign.pitches if pitch.sent_at is not None and pitch.status in {"sent"}]
                if not sent_pitches:
                    continue
                if all(pitch.sent_at <= threshold for pitch in sent_pitches):
                    due.append(campaign)
            return due

    def mark_followup_sent(self, campaign_id: str, journalist_id: str, *, provider: str, message_id: str, sent_at: datetime) -> None:
        with self._lock:
            campaign = self.campaigns[campaign_id]
            for pitch in campaign.pitches:
                if pitch.journalist_id == journalist_id:
                    pitch.follow_up_sent_at = sent_at
                    pitch.provider = provider
                    pitch.provider_message_id = message_id
                    pitch.status = "follow_up_sent"
                    break
            campaign.follow_up_sent_count += 1
            campaign.updated_at = sent_at
            campaign.status = "awaiting_response"

    def maybe_run_weekly_update(self, now: datetime) -> bool:
        with self._lock:
            if (now - self.last_weekly_update_at) < timedelta(days=7):
                return False
            self.last_weekly_update_at = now
            for index, journalist in enumerate(self.journalists):
                if index % 17 == 0:
                    journalist.freshness_score = min(1.0, round(journalist.freshness_score + 0.08, 2))
                    journalist.last_updated_at = now - timedelta(days=index % 5)
                elif index % 31 == 0:
                    journalist.freshness_score = max(0.2, round(journalist.freshness_score - 0.05, 2))
            for campaign in self.campaigns.values():
                campaign.last_weekly_update_at = now
                campaign.updated_at = now
            return True

    def to_status(self, campaign_id: str) -> dict[str, Any] | None:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            return None
        return campaign.to_status_payload()


STORE = CampaignStore()
