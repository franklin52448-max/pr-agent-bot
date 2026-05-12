from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ProductProfile(BaseModel):
    product_name: str = Field(..., min_length=1)
    company_name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    keywords: list[str] = Field(default_factory=list)
    target_beats: list[str] = Field(default_factory=list)
    target_regions: list[str] = Field(default_factory=list)
    target_outlets: list[str] = Field(default_factory=list)
    launch_angle: str | None = None
    contact_name: str | None = None
    contact_email: str = Field(..., min_length=3)
    website: HttpUrl | str | None = None
    media_kit_url: HttpUrl | str | None = None
    notes: str | None = None


class RegisterRequest(BaseModel):
    product: ProductProfile
    dry_run: bool = False
    max_journalists: int = Field(default=12, ge=1, le=100)


class MatchPreviewRequest(BaseModel):
    product: ProductProfile
    max_journalists: int = Field(default=12, ge=1, le=100)


class JournalistMatch(BaseModel):
    journalist_id: str
    name: str
    email: str
    outlet: str
    beat: str
    region: str
    score: float
    rationale: list[str]
    estimated_cost_usdc: str


class X402Quote(BaseModel):
    settlement: Literal["x402"] = "x402"
    currency: Literal["USDC"] = "USDC"
    pitch_count: int
    price_per_pitch_usdc: str
    total_usdc: str


class RegisterResponse(BaseModel):
    campaign_id: str
    dry_run: bool
    status: str
    pitch_count: int
    sent_count: int
    provider: str | None = None
    price_per_pitch_usdc: str
    total_usdc: str
    x402: X402Quote
    matches: list[JournalistMatch]


class MatchPreviewResponse(BaseModel):
    total_considered: int
    pitch_count: int
    price_per_pitch_usdc: str
    total_usdc: str
    x402: X402Quote
    matches: list[JournalistMatch]


class PitchStatus(BaseModel):
    journalist_id: str
    name: str
    email: str
    outlet: str
    beat: str
    score: float
    rationale: list[str]
    status: str
    sent_at: datetime | None = None
    follow_up_sent_at: datetime | None = None
    provider: str | None = None
    provider_message_id: str | None = None
    error: str | None = None


class CampaignStatusResponse(BaseModel):
    campaign_id: str
    status: str
    dry_run: bool
    created_at: datetime
    updated_at: datetime
    product: ProductProfile
    pitch_count: int
    sent_count: int
    response_count: int
    follow_up_sent_count: int
    last_response_at: datetime | None = None
    last_weekly_update_at: datetime | None = None
    price_per_pitch_usdc: str
    total_usdc: str
    x402: X402Quote
    pitches: list[PitchStatus]
