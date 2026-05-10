from __future__ import annotations

from dataclasses import dataclass

from .models import PREvaluationRequest, PREvaluationResponse


@dataclass(frozen=True)
class ScoreWeights:
    novelty: int = 18
    user_impact: int = 18
    technical_quality: int = 15
    evidence_quality: int = 12
    release_readiness: int = 12
    communication_readiness: int = 10
    risk: int = 15


WEIGHTS = ScoreWeights()


def _round_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def score_pr(request: PREvaluationRequest) -> PREvaluationResponse:
    signals = request.signals
    weighted = (
        signals.novelty * WEIGHTS.novelty
        + signals.user_impact * WEIGHTS.user_impact
        + signals.technical_quality * WEIGHTS.technical_quality
        + signals.evidence_quality * WEIGHTS.evidence_quality
        + signals.release_readiness * WEIGHTS.release_readiness
        + signals.communication_readiness * WEIGHTS.communication_readiness
        - signals.risk * WEIGHTS.risk
    )
    score = _round_score(weighted + 30)

    reasons: list[str] = []
    if signals.novelty >= 0.75:
        reasons.append('novelty is strong')
    if signals.user_impact >= 0.7:
        reasons.append('user impact is compelling')
    if signals.evidence_quality >= 0.7:
        reasons.append('supporting evidence is ready for external sharing')
    if signals.release_readiness < 0.4:
        reasons.append('release readiness is low')
    if signals.risk >= 0.6:
        reasons.append('risk profile is elevated')
    if request.human_review_required:
        reasons.append('human review explicitly required')

    if score >= 85 and not request.human_review_required:
        decision = 'auto_approve'
    elif score >= 70:
        decision = 'human_review'
    elif score >= 40:
        decision = 'revise_and_resubmit'
    else:
        decision = 'reject'

    outreach_recommended = score >= 80 and signals.communication_readiness >= 0.6 and signals.risk < 0.5
    outreach_angle = None
    if outreach_recommended:
        outreach_angle = _build_outreach_angle(request)
        reasons.append('journalist outreach is appropriate')

    metadata = {
        'weights': WEIGHTS.__dict__,
        'labels': request.pr.labels,
        'changed_files': request.pr.changed_files,
        'merged_at': request.pr.merged_at.isoformat() if request.pr.merged_at else None,
    }
    return PREvaluationResponse(
        score=score,
        decision=decision,
        reasons=reasons or ['no special flags raised'],
        outreach_recommended=outreach_recommended,
        outreach_angle=outreach_angle,
        metadata=metadata,
    )


def _build_outreach_angle(request: PREvaluationRequest) -> str:
    pr = request.pr
    if pr.release_notes:
        return f"Announce the update as a concrete product milestone: {pr.release_notes.strip()}"
    if pr.audience:
        audience = ', '.join(pr.audience[:3])
        return f"Frame the story around the audience impact for {audience}."
    return f"Position {pr.title} as a product and workflow improvement with clear user value."
