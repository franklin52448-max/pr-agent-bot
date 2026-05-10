from __future__ import annotations

from .campaigns import build_preview, get_catalog, score_match
from .models import JournalistProfile, OutreachRecommendation, OutreachRequest, OutreachResponse, MatchPreviewRequest, ProductRegistrationRequest


def _subject(pr_title: str, journalist: JournalistProfile) -> str:
    return f'Story idea: {pr_title} for {journalist.outlet}'


def _body(request: OutreachRequest, journalist: JournalistProfile, score: int) -> str:
    pr = request.pr
    recent_topic = journalist.recent_coverage_topics[0] if journalist.recent_coverage_topics else 'a recent story'
    return (
        f'Hi {journalist.name},\n\n'
        f'Your recent coverage of {recent_topic} suggests this could fit your beat.\n\n'
        f'Title: {pr.title}\n'
        f'Summary: {pr.summary}\n'
        f'Beat: {", ".join(journalist.beat) if journalist.beat else "product and tech"}\n'
        f'Relevance score: {score}/10\n\n'
        f'If this is not a fit, please unsubscribe using the campaign-level unsubscribe flow.'
    )


def build_outreach(request: OutreachRequest) -> OutreachResponse:
    journalists = request.journalists
    if not journalists:
        preview = build_preview(MatchPreviewRequest(product=ProductRegistrationRequest(
            product_name=request.pr.title,
            description=request.pr.summary,
            key_differentiators=request.pr.labels[:3],
            target_audience=request.pr.audience[:3],
            news_hooks=request.pr.release_notes.split(';') if request.pr.release_notes else [],
            budget_cap_usdc=0.0,
            dry_run=True,
        ), limit=10))
        recommendations = [
            OutreachRecommendation(
                journalist=match.journalist,
                score=match.relevance_score,
                angle=f'Pitch the story around {match.journalist.recent_coverage_topics[0] if match.journalist.recent_coverage_topics else "their beat"}.',
                subject=match.pitch_subject,
                body=match.pitch_body,
            )
            for match in preview.matches
        ]
        summary = f'Ranked {len(recommendations)} journalists from the built-in catalog for {request.pr.title}.'
        return OutreachResponse(top_pick=recommendations[0] if recommendations else None, recommendations=recommendations, summary=summary)

    recommendations: list[OutreachRecommendation] = []
    for journalist in journalists:
        score = max(1, min(10, int(round(score_match(ProductRegistrationRequest(
            product_name=request.pr.title,
            description=request.pr.summary,
            key_differentiators=request.pr.labels[:3],
            target_audience=request.pr.audience[:3],
            news_hooks=request.pr.release_notes.split(';') if request.pr.release_notes else [],
            budget_cap_usdc=0.0,
            dry_run=True,
        ), journalist)))))
        recommendations.append(
            OutreachRecommendation(
                journalist=journalist,
                score=score,
                angle=f'Frame {request.pr.title} as a useful story for {journalist.outlet}.',
                subject=_subject(request.pr.title, journalist),
                body=_body(request, journalist, score),
            )
        )

    recommendations.sort(key=lambda item: item.score, reverse=True)
    summary = f'Ranked {len(recommendations)} journalist profiles for {request.pr.title}.'
    return OutreachResponse(top_pick=recommendations[0] if recommendations else None, recommendations=recommendations, summary=summary)
