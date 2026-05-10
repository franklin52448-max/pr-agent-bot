from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PRSignals(BaseModel):
    novelty: float = Field(default=0.5, ge=0.0, le=1.0)
    user_impact: float = Field(default=0.5, ge=0.0, le=1.0)
    technical_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    release_readiness: float = Field(default=0.5, ge=0.0, le=1.0)
    communication_readiness: float = Field(default=0.5, ge=0.0, le=1.0)
    risk: float = Field(default=0.0, ge=0.0, le=1.0)


class PRArtifact(BaseModel):
    title: str
    summary: str
    repo: str | None = None
    branch: str | None = None
    url: str | None = None
    labels: list[str] = Field(default_factory=list)
    merged_at: datetime | None = None
    changed_files: list[str] = Field(default_factory=list)
    release_notes: str | None = None
    evidence_links: list[str] = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)


class PREvaluationRequest(BaseModel):
    pr: PRArtifact
    signals: PRSignals = Field(default_factory=PRSignals)
    human_review_required: bool = False


class PREvaluationResponse(BaseModel):
    score: int
    decision: Literal['auto_approve', 'human_review', 'revise_and_resubmit', 'reject']
    reasons: list[str]
    outreach_recommended: bool
    outreach_angle: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JournalistProfile(BaseModel):
    name: str
    outlet: str
    beat: list[str] = Field(default_factory=list)
    email: str | None = None
    x_handle: str | None = None
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str | None = None
    tier: Literal['Tier 1', 'Tier 2', 'Tier 3'] = 'Tier 3'
    publication: str | None = None
    recent_coverage_topics: list[str] = Field(default_factory=list)
    last_updated_at: datetime | None = None
    unsubscribed: bool = False


class JournalistRegistryEntry(JournalistProfile):
    publication: str
    recent_coverage_topics: list[str] = Field(default_factory=list)
    last_updated_at: datetime | None = None


class OutreachRequest(BaseModel):
    pr: PRArtifact
    journalists: list[JournalistProfile] = Field(default_factory=list)
    tone: Literal['objective', 'insightful', 'friendly'] = 'objective'


class OutreachRecommendation(BaseModel):
    journalist: JournalistProfile
    score: int
    angle: str
    subject: str
    body: str


class OutreachResponse(BaseModel):
    top_pick: OutreachRecommendation | None = None
    recommendations: list[OutreachRecommendation]
    summary: str


class SendWindow(BaseModel):
    timezone: str = 'UTC'
    start_hour: int = Field(default=9, ge=0, le=23)
    end_hour: int = Field(default=17, ge=1, le=24)


class ProductRegistrationRequest(BaseModel):
    product_name: str
    description: str
    key_differentiators: list[str] = Field(default_factory=list)
    target_audience: list[str] = Field(default_factory=list)
    news_hooks: list[str] = Field(default_factory=list)
    budget_cap_usdc: float = Field(default=0.0, ge=0.0)
    timezone: str = 'UTC'
    send_window: SendWindow = Field(default_factory=SendWindow)
    dry_run: bool = True
    client_reference: str | None = None


class JournalistMatch(BaseModel):
    journalist: JournalistRegistryEntry
    relevance_score: int = Field(ge=1, le=10)
    pitch_ready: bool
    pitch_subject: str
    pitch_body: str
    unsubscribe_url: str


class MatchPreviewRequest(BaseModel):
    product: ProductRegistrationRequest
    limit: int = Field(default=10, ge=1, le=25)
    include_unsubscribed: bool = False


class MatchPreviewResponse(BaseModel):
    matches: list[JournalistMatch]
    database_size: int
    dry_run: bool
    generated_at: datetime
    next_refresh_at: datetime


class CampaignRegistrationResponse(BaseModel):
    campaign_id: str
    product: ProductRegistrationRequest
    matches: list[JournalistMatch]
    database_size: int
    dry_run: bool
    budget_cap_usdc: float
    estimated_pitch_count: int
    estimated_cost_usdc: float
    generated_at: datetime
    next_refresh_at: datetime


class CampaignStatusResponse(BaseModel):
    campaign_id: str
    product: ProductRegistrationRequest
    state: Literal['draft', 'queued', 'sent', 'running', 'paused', 'completed']
    dry_run: bool
    database_size: int
    matched_journalists: int
    sent_pitches: int
    queued_pitches: int
    opened_count: int
    replied_count: int
    follow_up_sent: bool
    follow_up_due_at: datetime | None = None
    next_send_at: datetime | None = None
    budget_cap_usdc: float
    budget_spent_usdc: float
    unsubscribe_count: int
    last_refresh_at: datetime
    recommendations: list[JournalistMatch] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)


class OutreachEventRequest(BaseModel):
    campaign_id: str
    journalist_email: str
    event_type: Literal['open', 'reply', 'unsubscribe']
    occurred_at: datetime | None = None


class UnsubscribeRequest(BaseModel):
    campaign_id: str | None = None
    journalist_email: str
    reason: str | None = None


class X402QuoteRequest(BaseModel):
    route: str
    purpose: str
    price_usdc: float | None = None


class X402QuoteResponse(BaseModel):
    route: str
    amount_usdc: float
    chain_id: int
    token: str
    treasury: str
    memo: str


class X402PaymentEnvelope(BaseModel):
    chain_id: int
    token_address: str
    treasury_address: str
    amount_usdc: float
    payer_address: str | None = None
    tx_hash: str | None = None
    nonce: str | None = None
    signature: str | None = None
    settlement_status: Literal['pending', 'settled', 'failed'] | None = None
    confirmations: int | None = None


class X402VerifyRequest(BaseModel):
    route: str
    payment: X402PaymentEnvelope


class X402VerifyResponse(BaseModel):
    ok: bool
    reason: str
    accepted: bool
    details: dict[str, Any] = Field(default_factory=dict)
