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


class OutreachRequest(BaseModel):
    pr: PRArtifact
    journalists: list[JournalistProfile]
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
