from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .config import settings
from .models import (
    OutreachRequest,
    PREvaluationRequest,
    PRArtifact,
    X402QuoteRequest,
    X402QuoteResponse,
    X402VerifyRequest,
    X402VerifyResponse,
)
from .outreach import build_outreach
from .payments import quote_payment, verify_payment
from .scoring import score_pr

app = FastAPI(title=settings.app_name, version='1.0.0')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'service': settings.app_name}


@app.post('/v1/prs/evaluate')
def evaluate_pr(payload: PREvaluationRequest) -> dict:
    return score_pr(payload).model_dump()


@app.post('/v1/prs/brief')
def brief_pr(payload: OutreachRequest) -> dict:
    return build_outreach(payload).model_dump()


@app.post('/v1/outreach/journalists')
def rank_journalists(payload: OutreachRequest) -> dict:
    return build_outreach(payload).model_dump()


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
    return {'message': 'Zero-human PR agent is running'}
