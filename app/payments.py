from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .config import settings


def quote_usdc(pitch_count: int) -> dict[str, str | int]:
    total = (settings.price_per_pitch_usdc * Decimal(pitch_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "settlement": "x402",
        "currency": "USDC",
        "pitch_count": pitch_count,
        "price_per_pitch_usdc": f"{settings.price_per_pitch_usdc:.2f}",
        "total_usdc": f"{total:.2f}",
    }


def quote_total(pitch_count: int) -> Decimal:
    return (settings.price_per_pitch_usdc * Decimal(pitch_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
