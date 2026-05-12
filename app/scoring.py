from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import re
from typing import Iterable

from .models import ProductProfile
from .seed import BEAT_PROFILES
from .campaigns import JournalistRecord

WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in WORD_RE.findall(value.lower()) if token}


def _normalize(values: Iterable[str]) -> set[str]:
    output: set[str] = set()
    for value in values:
        output |= _tokens(value)
    return output


def score_journalist(product: ProductProfile, journalist: JournalistRecord) -> tuple[float, list[str]]:
    score = 0.0
    rationale: list[str] = []

    product_terms = _normalize(
        [
            product.product_name,
            product.company_name,
            product.description,
            product.category,
            product.launch_angle or "",
            *product.keywords,
            *product.target_beats,
            *product.target_regions,
            *product.target_outlets,
        ]
    )

    journalist_terms = _normalize([
        journalist.name,
        journalist.outlet,
        journalist.beat,
        journalist.region,
        *journalist.tags,
    ])

    shared = product_terms & journalist_terms
    if shared:
        score += min(35.0, 10.0 + len(shared) * 4.5)
        rationale.append(f"shared terms: {', '.join(sorted(list(shared))[:5])}")

    beat_profile = BEAT_PROFILES.get(journalist.beat, {})
    beat_keywords = set(map(str.lower, beat_profile.get("keywords", [])))
    beat_terms = product_terms & beat_keywords
    if beat_terms:
        score += min(30.0, 12.0 + len(beat_terms) * 5)
        rationale.append(f"beat fit: {', '.join(sorted(list(beat_terms))[:5])}")

    if product.category.lower() == journalist.beat.lower():
        score += 20.0
        rationale.append("direct category match")

    if journalist.outlet in product.target_outlets:
        score += 25.0
        rationale.append("target outlet match")

    if journalist.region in {region.lower() for region in product.target_regions}:
        score += 12.0
        rationale.append("target region match")

    if journalist.seniority == "editor":
        score += 4.0
        rationale.append("editor-level contact")
    elif journalist.seniority == "senior":
        score += 2.0

    days_since_update = max(0, (datetime.now(timezone.utc) - journalist.last_updated_at).days)
    freshness_bonus = max(0.0, 8.0 - days_since_update * 0.35)
    if freshness_bonus:
        score += freshness_bonus
        rationale.append(f"freshness bonus {freshness_bonus:.1f}")

    if not rationale:
        rationale.append("general products reporter fit")
        score += 5.0

    return round(min(score, 100.0), 2), rationale


def rank_journalists(product: ProductProfile, journalists: Iterable[JournalistRecord], limit: int) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    for journalist in journalists:
        score, rationale = score_journalist(product, journalist)
        ranked.append(
            {
                **asdict(journalist),
                "score": score,
                "rationale": rationale,
            }
        )
    ranked.sort(key=lambda item: (item["score"], item["freshness_score"]), reverse=True)
    return ranked[:limit]
