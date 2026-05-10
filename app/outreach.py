from __future__ import annotations

from .models import JournalistProfile, OutreachRecommendation, OutreachRequest, OutreachResponse


STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'into', 'that', 'this', 'your', 'their', 'about', 'into',
    'pr', 'agent', 'zero', 'human', 'update', 'release', 'launch', 'feature', 'product'
}


def _keywords(text: str) -> set[str]:
    tokens = {
        token.strip('.,:;!?()[]{}"\'').lower()
        for token in text.split()
        if token.strip('.,:;!?()[]{}"\'').lower() not in STOPWORDS and len(token.strip('.,:;!?()[]{}"\'')) > 2
    }
    return tokens


def _match_score(pr_terms: set[str], journalist: JournalistProfile) -> int:
    beat_terms = {term.lower() for term in journalist.beat}
    overlap = len(pr_terms & beat_terms)
    score = int(round(journalist.relevance * 70 + overlap * 12))
    if journalist.notes:
        score += min(10, len(journalist.notes) // 50)
    return max(0, min(100, score))


def _angle(request: OutreachRequest, journalist: JournalistProfile) -> str:
    pr = request.pr
    beats = ', '.join(journalist.beat) if journalist.beat else 'product and tech'
    if pr.release_notes:
        return f"Lead with the release note: {pr.release_notes.strip()}"
    if pr.audience:
        return f"Focus on user impact for {', '.join(pr.audience[:3])}"
    return f"Frame {pr.title} as a clear {beats} story with measurable utility."


def _subject(pr_title: str, journalist: JournalistProfile) -> str:
    return f"Story idea: {pr_title}"


def _body(request: OutreachRequest, journalist: JournalistProfile, angle: str) -> str:
    pr = request.pr
    greeting = f"Hi {journalist.name},"
    opening = {
        'objective': 'Sharing a concise update that may fit your coverage.',
        'insightful': 'Sharing a story angle that may be useful for your readers.',
        'friendly': 'Thought this might be relevant for your beat.',
    }[request.tone]
    return (
        f"{greeting}\n\n"
        f"{opening}\n\n"
        f"Title: {pr.title}\n"
        f"Summary: {pr.summary}\n"
        f"Angle: {angle}\n"
        f"Relevant beats: {', '.join(journalist.beat) if journalist.beat else 'product, AI, and developer tools'}\n"
        f"Outlet: {journalist.outlet}\n"
        f"Contact: {journalist.email or 'available on request'}\n"
    )


def build_outreach(request: OutreachRequest) -> OutreachResponse:
    pr_terms = _keywords(f"{request.pr.title} {request.pr.summary} {' '.join(request.pr.labels)}")
    recommendations: list[OutreachRecommendation] = []
    for journalist in request.journalists:
        score = _match_score(pr_terms, journalist)
        angle = _angle(request, journalist)
        recommendations.append(
            OutreachRecommendation(
                journalist=journalist,
                score=score,
                angle=angle,
                subject=_subject(request.pr.title, journalist),
                body=_body(request, journalist, angle),
            )
        )

    recommendations.sort(key=lambda item: item.score, reverse=True)
    top_pick = recommendations[0] if recommendations else None
    summary = (
        f"Ranked {len(recommendations)} journalist profiles for {request.pr.title}."
        + (f" Top match: {top_pick.journalist.name} ({top_pick.score}/100)." if top_pick else '')
    )
    return OutreachResponse(top_pick=top_pick, recommendations=recommendations, summary=summary)
