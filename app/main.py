from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .campaigns import (
    build_preview,
    get_campaign_status,
    get_catalog,
    next_refresh_at,
    record_event,
    register_product,
    refresh_catalog,
    send_campaign,
    unsubscribe_journalist,
)
from .config import settings
from .models import (
    MatchPreviewRequest,
    OutreachEventRequest,
    OutreachRequest,
    PRArtifact,
    PREvaluationRequest,
    ProductRegistrationRequest,
    UnsubscribeRequest,
    X402QuoteRequest,
    X402QuoteResponse,
    X402VerifyRequest,
    X402VerifyResponse,
)
from .outreach import build_outreach
from .payments import quote_payment, verify_payment
from .scoring import score_pr

app = FastAPI(title=settings.app_name, version='1.1.0')


@app.on_event('startup')
def _prime_catalog() -> None:
    refresh_catalog(force=False)


@app.get('/health')
def health() -> dict[str, str]:
    return {
        'status': 'ok',
        'service': settings.app_name,
        'journalist_catalog_size': str(len(get_catalog())),
    }


@app.post('/v1/prs/evaluate')
def evaluate_pr(payload: PREvaluationRequest) -> dict:
    return score_pr(payload).model_dump()


@app.post('/v1/prs/brief')
def brief_pr(payload: OutreachRequest) -> dict:
    return build_outreach(payload).model_dump()


@app.post('/v1/outreach/journalists')
def rank_journalists(payload: OutreachRequest) -> dict:
    return build_outreach(payload).model_dump()


@app.post('/v1/products/register')
def register_product_route(payload: ProductRegistrationRequest) -> dict:
    return register_product(payload).model_dump()


@app.post('/v1/products/match-preview')
def match_preview_route(payload: MatchPreviewRequest) -> dict:
    return build_preview(payload).model_dump()


@app.get('/v1/campaigns/{campaign_id}/status')
def campaign_status_route(campaign_id: str) -> dict:
    try:
        return get_campaign_status(campaign_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/v1/campaigns/{campaign_id}/send')
def campaign_send_route(campaign_id: str) -> dict:
    try:
        return send_campaign(campaign_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/v1/campaigns/events')
def campaign_event_route(payload: OutreachEventRequest) -> dict:
    try:
        return record_event(payload).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/v1/journalists/unsubscribe')
def journalist_unsubscribe_route(payload: UnsubscribeRequest) -> dict:
    return unsubscribe_journalist(payload)


@app.post('/v1/payments/x402/quote', response_model=X402QuoteResponse)
def payment_quote(payload: X402QuoteRequest) -> X402QuoteResponse:
    return quote_payment(payload)


@app.post('/v1/payments/x402/verify', response_model=X402VerifyResponse)
def payment_verify(payload: X402VerifyRequest) -> X402VerifyResponse:
    return verify_payment(payload)


@app.post('/v1/prs/evaluate-and-brief')
def evaluate_and_brief(payload: dict) -> dict:
    try:
        pr = PRArtifact(**payload['pr'])
        signals = payload.get('signals', {})
        human_review_required = bool(payload.get('human_review_required', False))
        journalists = payload.get('journalists', [])
        tone = payload.get('tone', 'objective')
    except Exception as exc:  # pragma: no cover - request validation fallback
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    evaluation = score_pr(PREvaluationRequest(pr=pr, signals=signals, human_review_required=human_review_required))
    outreach = build_outreach(OutreachRequest(pr=pr, journalists=journalists, tone=tone))
    return {'evaluation': evaluation.model_dump(), 'outreach': outreach.model_dump()}


@app.get('/')
def root() -> dict[str, str]:
    return {
        'message': 'Zero-human PR agent is running',
        'next_refresh_at': next_refresh_at().isoformat(),
    }
