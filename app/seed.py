from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import Random

from .campaigns import JournalistRecord

BEAT_PROFILES: dict[str, dict[str, object]] = {
    "ai": {
        "outlet": "Signal AI",
        "domain": "signalai.news",
        "keywords": ["ai", "machine learning", "llm", "agents", "robotics", "model"],
        "regions": ["global", "north america", "europe"],
    },
    "defi": {
        "outlet": "Chain Desk",
        "domain": "chaindesk.news",
        "keywords": ["defi", "crypto", "web3", "token", "blockchain", "wallet"],
        "regions": ["global", "north america", "asia"],
    },
    "fintech": {
        "outlet": "Ledger Weekly",
        "domain": "ledgerweekly.news",
        "keywords": ["fintech", "payments", "banking", "lending", "embedded finance"],
        "regions": ["north america", "europe", "latam"],
    },
    "cybersecurity": {
        "outlet": "Zero Trust Daily",
        "domain": "zerotrustdaily.news",
        "keywords": ["security", "cybersecurity", "privacy", "breach", "threat", "ransomware"],
        "regions": ["north america", "europe", "global"],
    },
    "climate": {
        "outlet": "Climate Circuit",
        "domain": "climatecircuit.news",
        "keywords": ["climate", "energy", "carbon", "sustainability", "cleantech"],
        "regions": ["europe", "north america", "global"],
    },
    "consumer tech": {
        "outlet": "Launch Loop",
        "domain": "launchloop.news",
        "keywords": ["consumer", "apps", "gadget", "startup", "mobile", "product"],
        "regions": ["north america", "europe", "asia"],
    },
    "health tech": {
        "outlet": "Vital Byte",
        "domain": "vitalbyte.news",
        "keywords": ["health", "biotech", "medtech", "care", "diagnostics"],
        "regions": ["north america", "europe", "global"],
    },
    "developer tools": {
        "outlet": "Build Mode",
        "domain": "buildmode.news",
        "keywords": ["devtools", "api", "platform", "infra", "open source", "developer"],
        "regions": ["north america", "europe", "asia"],
    },
}

FIRST_NAMES = [
    "Avery", "Jordan", "Casey", "Morgan", "Taylor", "Riley", "Quinn", "Parker",
    "Cameron", "Drew", "Reese", "Blake", "Jamie", "Robin", "Hayden", "Kai",
    "Rowan", "Emerson", "Sage", "Ariel", "Noel", "Logan", "Skyler", "Marin", "Tatum",
]
LAST_NAMES = [
    "Adams", "Bennett", "Cole", "Diaz", "Evans", "Foster", "Grant", "Hayes", "Ibrahim", "Jensen",
]
SENIORITY = ["staff", "senior", "editor"]


def generate_journalist_seed() -> list[JournalistRecord]:
    rng = Random(402)
    journalists: list[JournalistRecord] = []
    now = datetime.now(timezone.utc)
    for beat_index, (beat, profile) in enumerate(BEAT_PROFILES.items()):
        outlet = str(profile["outlet"])
        domain = str(profile["domain"])
        keywords = list(profile["keywords"])
        regions = list(profile["regions"])
        for first_index, first in enumerate(FIRST_NAMES):
            for last_index, last in enumerate(LAST_NAMES):
                seq = beat_index * 250 + first_index * 10 + last_index + 1
                handle = f"{first.lower()}.{last.lower()}.{beat.replace(' ', '')}.{seq}"
                journalists.append(
                    JournalistRecord(
                        journalist_id=f"j{seq:04d}",
                        name=f"{first} {last}",
                        email=f"{handle}@{domain}",
                        outlet=f"{outlet} {last_index % 5 + 1}",
                        beat=beat,
                        region=regions[(first_index + last_index) % len(regions)],
                        tags=keywords + [beat, "launch", "news", "products"],
                        seniority=SENIORITY[(first_index + last_index + beat_index) % len(SENIORITY)],
                        freshness_score=round(rng.uniform(0.35, 0.98), 2),
                        last_updated_at=now - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 23)),
                    )
                )
    return journalists
