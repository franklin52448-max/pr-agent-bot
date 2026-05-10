from __future__ import annotations

import hashlib
import itertools
import math
import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings
from .models import (
    CampaignRegistrationResponse,
    CampaignStatusResponse,
    JournalistMatch,
    JournalistProfile,
    JournalistRegistryEntry,
    MatchPreviewRequest,
    MatchPreviewResponse,
    OutreachEventRequest,
    ProductRegistrationRequest,
    SendWindow,
    UnsubscribeRequest,
)

STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'into', 'that', 'this', 'your', 'their', 'about', 'into',
    'pr', 'agent', 'zero', 'human', 'update', 'release', 'launch', 'feature', 'product', 'a', 'an',
    'to', 'of', 'on', 'in', 'by', 'is', 'it', 'as', 'at', 'be', 'or', 'we', 'you', 'our', 'more'
}

BEATS = ['AI', 'DeFi', 'infrastructure', 'regulation', 'gaming', 'security', 'consumer', 'developer tools']
TIER_SOURCES = {
    'Tier 1': ['CoinDesk', 'TechCrunch'],
    'Tier 2': ['The Block', 'Decrypt', 'Axios Pro'],
    'Tier 3': ['Niche Crypto Blog', 'AI Weekly', 'Protocol Notes', 'Infra Digest'],
}
TOPIC_BANK = {
    'AI': ['foundation models', 'agents', 'model governance', 'enterprise AI'],
    'DeFi': ['liquidity', 'protocol design', 'onchain finance', 'token incentives'],
    'infrastructure': ['scaling', 'tooling', 'platform reliability', 'developer experience'],
    'regulation': ['policy', 'compliance', 'SEC', 'consumer protection'],
    'gaming': ['live ops', 'economies', 'creator tools', 'play-to-own'],
    'security': ['threat detection', 'incident response', 'wallet safety', 'fraud prevention'],
    'consumer': ['retention', 'mobile UX', 'creator monetization', 'community growth'],
    'developer tools': ['APIs', 'SDKs', 'workflow automation', 'integration layers'],
}
PUBLICATION_TZ = 'UTC'
PITCH_COST_USDC = 0.5
FOLLOW_UP_DAYS = 3
CATALOG_REFRESH_INTERVAL = timedelta(days=7)

CAMPAIGNS: dict[str, dict[str, Any]] = {}
UNSUBSCRIBES: set[str] = set()
EVENT_LOGS: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
_LAST_REFRESH_AT = datetime.now(UTC)
_CATALOG = []


def _tokenize(text: str) -> set[str]:
    return {
        token.strip('.,:;!?()[]{}"\'').lower()
        for token in text.split()
        if token.strip('.,:;!?()[]{}"\'').lower() and token.strip('.,:;!?()[]{}"\'').lower() not in STOPWORDS
    }


def _choose(items: list[str], index: int) -> str:
    return items[index % len(items)]


def _tier(index: int) -> str:
    if index % 11 == 0:
        return 'Tier 1'
    if index % 4 == 0:
        return 'Tier 2'
    return 'Tier 3'


def _build_catalog(size: int | None = None) -> list[JournalistRegistryEntry]:
    size = size or settings.journalist_catalog_size
    catalog: list[JournalistRegistryEntry] = []
    for index in range(size):
        beat = BEATS[index % len(BEATS)]
        tier = _tier(index)
        publication = _choose(TIER_SOURCES[tier], index)
        coverage = TOPIC_BANK[beat]
        first_name = ['Alex', 'Jordan', 'Taylor', 'Sam', 'Morgan', 'Casey', 'Riley', 'Jamie'][index % 8]
        last_name = f'Writer{index + 1:04d}'
        handle = f'@{first_name.lower()}{index + 1:04d}'
        email = f'{first_name.lower()}.{index + 1:04d}@examplemedia.com'
        relevance = round(0.45 + (index % 10) * 0.045, 3)
        catalog.append(
            JournalistRegistryEntry(
                name=f'{first_name} {last_name}',
                outlet=publication,
                beat=[beat, _choose(BEATS, index + 3)],
                email=email,
                x_handle=handle,
                relevance=min(1.0, relevance),
                notes=f'Covers {beat} and closely related launches.',
                tier=tier,
                publication=publication,
                recent_coverage_topics=[coverage[index % len(coverage)], coverage[(index + 1) % len(coverage)]],
                last_updated_at=_LAST_REFRESH_AT,
            )
        )
    return catalog


def _ensure_catalog() -> list[JournalistRegistryEntry]:
    global _CATALOG, _LAST_REFRESH_AT
    now = datetime.now(UTC)
    if not _CATALOG:
        _CATALOG = _build_catalog()
        _LAST_REFRESH_AT = now
    elif now - _LAST_REFRESH_AT >= CATALOG_REFRESH_INTERVAL:
        _CATALOG = refresh_catalog()
    return _CATALOG


def refresh_catalog(force: bool = False) -> list[JournalistRegistryEntry]:
    global _CATALOG, _LAST_REFRESH_AT
    now = datetime.now(UTC)
    if not force and _CATALOG and now - _LAST_REFRESH_AT < CATALOG_REFRESH_INTERVAL:
        return _CATALOG

    week_fingerprint = int(now.strftime('%G%V'))
    refreshed: list[JournalistRegistryEntry] = []
    for index, journalist in enumerate(_CATALOG or _build_catalog()):
        beat = journalist.beat[0] if journalist.beat else BEATS[index % len(BEATS)]
        topic_bank = TOPIC_BANK.get(beat, TOPIC_BANK['developer tools'])
        topic_seed = (week_fingerprint + index) % len(topic_bank)
        journalist.recent_coverage_topics = [
            topic_bank[topic_seed],
            topic_bank[(topic_seed + 1) % len(topic_bank)],
        ]
        journalist.last_updated_at = now
        journalist.notes = f'{journalist.notes or ""} Updated weekly on {now.date().isoformat()}'.strip()
        refreshed.append(journalist)
    _CATALOG = refreshed
    _LAST_REFRESH_AT = now
    return refreshed


def get_catalog() -> list[JournalistRegistryEntry]:
    return _ensure_catalog()


def next_refresh_at() -> datetime:
    return _LAST_REFRESH_AT + CATALOG_REFRESH_INTERVAL


def _product_terms(product: ProductRegistrationRequest) -> set[str]:
    text = ' '.join([
        product.product_name,
        product.description,
        ' '.join(product.key_differentiators),
        ' '.join(product.target_audience),
        ' '.join(product.news_hooks),
    ])
    return _tokenize(text)


def _journalist_terms(journalist: JournalistProfile) -> set[str]:
    text = ' '.join([
        journalist.outlet,
        journalist.publication or '',
        ' '.join(journalist.beat),
        ' '.join(journalist.recent_coverage_topics),
        journalist.notes or '',
        journalist.name,
    ])
    return _tokenize(text)


def score_match(product: ProductRegistrationRequest, journalist: JournalistProfile) -> int:
    product_terms = _product_terms(product)
    journalist_terms = _journalist_terms(journalist)
    overlap = len(product_terms & journalist_terms)
    beat_overlap = len(product_terms & {beat.lower() for beat in journalist.beat})
    topic_overlap = len(product_terms & {topic.lower() for topic in journalist.recent_coverage_topics})
    tier_bonus = {'Tier 1': 3, 'Tier 2': 2, 'Tier 3': 1}.get(journalist.tier, 1)
    relevance_bonus = int(round(journalist.relevance * 3))
    raw = 1 + (overlap * 1.5) + (beat_overlap * 2) + (topic_overlap * 2.5) + tier_bonus + relevance_bonus
    return max(1, min(10, int(round(raw))))


def _send_window(send_window: SendWindow | None, timezone_name: str | None = None) -> SendWindow:
    if send_window is not None:
        return send_window
    return SendWindow(
        timezone=timezone_name or settings.default_send_window_timezone,
        start_hour=settings.default_send_window_start_hour,
        end_hour=settings.default_send_window_end_hour,
    )


def _window_timezone(send_window: SendWindow) -> ZoneInfo:
    try:
        return ZoneInfo(send_window.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo('UTC')


def _within_send_window(moment: datetime, send_window: SendWindow) -> bool:
    local = moment.astimezone(_window_timezone(send_window))
    if local.weekday() >= 5:
        return False
    return send_window.start_hour <= local.hour < send_window.end_hour


def _next_send_window(moment: datetime, send_window: SendWindow) -> datetime:
    tz = _window_timezone(send_window)
    local = moment.astimezone(tz)
    candidate = local
    if local.hour >= send_window.end_hour or local.weekday() >= 5:
        candidate = candidate.replace(hour=send_window.start_hour, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif local.hour < send_window.start_hour:
        candidate = candidate.replace(hour=send_window.start_hour, minute=0, second=0, microsecond=0)
    while candidate.weekday() >= 5:
        candidate = candidate + timedelta(days=1)
        candidate = candidate.replace(hour=send_window.start_hour, minute=0, second=0, microsecond=0)
    return candidate.astimezone(UTC)


def _unsubscribe_url(journalist: JournalistProfile) -> str:
    email = journalist.email or journalist.x_handle or journalist.name
    token = hashlib.sha256(email.lower().encode('utf-8')).hexdigest()[:16]
    return f'/v1/journalists/unsubscribe?token={token}'


def _pitch_subject(product: ProductRegistrationRequest, journalist: JournalistProfile) -> str:
    beat = journalist.beat[0] if journalist.beat else 'tech'
    return f'{product.product_name} for your {beat} coverage'


def _pitch_body(product: ProductRegistrationRequest, journalist: JournalistProfile, score: int) -> str:
    recent_topic = journalist.recent_coverage_topics[0] if journalist.recent_coverage_topics else 'a recent story'
    differentiators = '; '.join(product.key_differentiators[:3]) or 'a focused product update'
    audience = ', '.join(product.target_audience[:3]) or 'readers in your beat'
    hooks = '; '.join(product.news_hooks[:2]) or 'no current news hook'
    return (
        f'Hi {journalist.name},\n\n'
        f'I’m reaching out because your recent coverage of {recent_topic} lines up with {product.product_name}.\n\n'
        f'What’s new: {product.description}\n'
        f'Why it fits: {differentiators}\n'
        f'Target audience: {audience}\n'
        f'News hooks: {hooks}\n'
        f'Relevance score: {score}/10\n\n'
        f'If this is not a fit, you can unsubscribe here: {_unsubscribe_url(journalist)}\n'
        f'This note is intended to comply with CAN-SPAM and keep outreach concise.'
    )


def _matching_journalists(product: ProductRegistrationRequest, include_unsubscribed: bool = False) -> list[tuple[JournalistRegistryEntry, int]]:
    matches: list[tuple[JournalistRegistryEntry, int]] = []
    for journalist in get_catalog():
        if not include_unsubscribed and journalist.email and journalist.email.lower() in UNSUBSCRIBES:
            continue
        score = score_match(product, journalist)
        matches.append((journalist, score))
    matches.sort(key=lambda item: (item[1], item[0].tier == 'Tier 1', item[0].relevance), reverse=True)
    return matches


def build_preview(request: MatchPreviewRequest) -> MatchPreviewResponse:
    ranked = _matching_journalists(request.product, include_unsubscribed=request.include_unsubscribed)
    matches = [
        JournalistMatch(
            journalist=journalist,
            relevance_score=score,
            pitch_ready=score >= 7,
            pitch_subject=_pitch_subject(request.product, journalist),
            pitch_body=_pitch_body(request.product, journalist, score),
            unsubscribe_url=_unsubscribe_url(journalist),
        )
        for journalist, score in ranked[: request.limit]
    ]
    now = datetime.now(UTC)
    return MatchPreviewResponse(
        matches=matches,
        database_size=len(get_catalog()),
        dry_run=True,
        generated_at=now,
        next_refresh_at=next_refresh_at(),
    )


def register_product(product: ProductRegistrationRequest) -> CampaignRegistrationResponse:
    campaign_id = uuid.uuid4().hex[:12]
    preview = build_preview(MatchPreviewRequest(product=product, limit=10, include_unsubscribed=False))
    estimated_pitch_count = sum(1 for match in preview.matches if match.pitch_ready)
    estimated_cost = round(estimated_pitch_count * PITCH_COST_USDC, 2)
    now = datetime.now(UTC)
    CAMPAIGNS[campaign_id] = {
        'campaign_id': campaign_id,
        'product': product.model_dump(),
        'created_at': now,
        'state': 'draft' if product.dry_run else 'queued',
        'dry_run': product.dry_run,
        'matches': [match.model_dump() for match in preview.matches],
        'sent_pitches': 0,
        'queued_pitches': estimated_pitch_count,
        'opened_count': 0,
        'replied_count': 0,
        'follow_up_sent': False,
        'follow_up_due_at': now + timedelta(days=FOLLOW_UP_DAYS),
        'next_send_at': None if product.dry_run else _next_send_window(now, _send_window(product.send_window, product.timezone)),
        'budget_cap_usdc': product.budget_cap_usdc,
        'budget_spent_usdc': 0.0,
        'unsubscribe_count': 0,
        'report': {
            'compliance': 'CAN-SPAM unsubscribe text included on all pitches',
            'pricing': {'pitch_cost_usdc': PITCH_COST_USDC, 'budget_cap_usdc': product.budget_cap_usdc},
        },
        'send_window': _send_window(product.send_window, product.timezone).model_dump(),
    }
    return CampaignRegistrationResponse(
        campaign_id=campaign_id,
        product=product,
        matches=preview.matches,
        database_size=preview.database_size,
        dry_run=product.dry_run,
        budget_cap_usdc=product.budget_cap_usdc,
        estimated_pitch_count=estimated_pitch_count,
        estimated_cost_usdc=estimated_cost,
        generated_at=now,
        next_refresh_at=preview.next_refresh_at,
    )


def _advance_campaign(campaign: dict[str, Any]) -> None:
    now = datetime.now(UTC)
    if campaign['state'] != 'draft' and not campaign['dry_run']:
        follow_up_due_at = campaign.get('follow_up_due_at')
        if (
            follow_up_due_at
            and not campaign.get('follow_up_sent')
            and campaign.get('replied_count', 0) == 0
            and now >= follow_up_due_at
            and campaign.get('sent_pitches', 0) > 0
        ):
            campaign['follow_up_sent'] = True
            campaign['report']['follow_up'] = {
                'sent_at': now.isoformat(),
                'trigger': 'no-reply-after-3-days',
            }
        if campaign.get('budget_spent_usdc', 0.0) >= campaign.get('budget_cap_usdc', 0.0) > 0:
            campaign['state'] = 'paused'
        elif campaign.get('replied_count', 0) > 0:
            campaign['state'] = 'completed'
        elif campaign.get('sent_pitches', 0) > 0:
            campaign['state'] = 'running'


def get_campaign_status(campaign_id: str) -> CampaignStatusResponse:
    if campaign_id not in CAMPAIGNS:
        raise KeyError(f'campaign {campaign_id} not found')
    campaign = CAMPAIGNS[campaign_id]
    _advance_campaign(campaign)
    product = ProductRegistrationRequest(**campaign['product'])
    return CampaignStatusResponse(
        campaign_id=campaign_id,
        product=product,
        state=campaign['state'],
        dry_run=campaign['dry_run'],
        database_size=len(get_catalog()),
        matched_journalists=len(campaign['matches']),
        sent_pitches=campaign['sent_pitches'],
        queued_pitches=campaign['queued_pitches'],
        opened_count=campaign['opened_count'],
        replied_count=campaign['replied_count'],
        follow_up_sent=campaign['follow_up_sent'],
        follow_up_due_at=campaign.get('follow_up_due_at'),
        next_send_at=campaign.get('next_send_at'),
        budget_cap_usdc=campaign['budget_cap_usdc'],
        budget_spent_usdc=campaign['budget_spent_usdc'],
        unsubscribe_count=campaign['unsubscribe_count'],
        last_refresh_at=_LAST_REFRESH_AT,
        recommendations=[JournalistMatch(**match) for match in campaign['matches']],
        report=campaign['report'],
    )


def send_campaign(campaign_id: str) -> CampaignStatusResponse:
    if campaign_id not in CAMPAIGNS:
        raise KeyError(f'campaign {campaign_id} not found')
    campaign = CAMPAIGNS[campaign_id]
    if campaign['dry_run']:
        return get_campaign_status(campaign_id)
    product = ProductRegistrationRequest(**campaign['product'])
    send_window = SendWindow(**campaign['send_window'])
    now = datetime.now(UTC)
    if not _within_send_window(now, send_window):
        campaign['next_send_at'] = _next_send_window(now, send_window)
        campaign['state'] = 'queued'
        campaign['report']['dispatch'] = {'status': 'queued', 'next_send_at': campaign['next_send_at'].isoformat()}
        return get_campaign_status(campaign_id)

    sent = 0
    for match in campaign['matches']:
        if match['relevance_score'] < 7:
            continue
        email = (match['journalist'].get('email') or '').lower()
        if email and email in UNSUBSCRIBES:
            continue
        projected_cost = campaign['budget_spent_usdc'] + PITCH_COST_USDC
        if campaign['budget_cap_usdc'] and projected_cost > campaign['budget_cap_usdc'] + 1e-9:
            campaign['state'] = 'paused'
            campaign['report']['dispatch'] = {
                'status': 'budget-exhausted',
                'sent_pitches': sent,
                'budget_spent_usdc': round(campaign['budget_spent_usdc'], 2),
            }
            break
        sent += 1
        campaign['budget_spent_usdc'] = round(projected_cost, 2)
        campaign['sent_pitches'] += 1
        campaign['queued_pitches'] = max(0, campaign['queued_pitches'] - 1)
        EVENT_LOGS[campaign_id].append(
            {
                'event_type': 'sent',
                'journalist_email': email,
                'occurred_at': now.isoformat(),
                'subject': match['pitch_subject'],
            }
        )

    campaign['state'] = 'sent' if sent else 'queued'
    campaign['report']['dispatch'] = {
        'status': 'sent' if sent else 'queued',
        'sent_pitches': sent,
        'pitch_cost_usdc': PITCH_COST_USDC,
        'budget_spent_usdc': campaign['budget_spent_usdc'],
        'send_window_timezone': send_window.timezone,
    }
    return get_campaign_status(campaign_id)


def record_event(event: OutreachEventRequest) -> CampaignStatusResponse:
    if event.campaign_id not in CAMPAIGNS:
        raise KeyError(f'campaign {event.campaign_id} not found')
    campaign = CAMPAIGNS[event.campaign_id]
    occurred_at = event.occurred_at or datetime.now(UTC)
    email = event.journalist_email.lower()
    EVENT_LOGS[event.campaign_id].append(
        {
            'event_type': event.event_type,
            'journalist_email': email,
            'occurred_at': occurred_at.isoformat(),
        }
    )
    if event.event_type == 'open':
        campaign['opened_count'] += 1
    elif event.event_type == 'reply':
        campaign['replied_count'] += 1
        campaign['report']['response'] = {'last_reply_at': occurred_at.isoformat(), 'journalist_email': email}
    elif event.event_type == 'unsubscribe':
        campaign['unsubscribe_count'] += 1
        UNSUBSCRIBES.add(email)
        campaign['report'].setdefault('unsubscribes', []).append({'journalist_email': email, 'occurred_at': occurred_at.isoformat()})
    return get_campaign_status(event.campaign_id)


def unsubscribe_journalist(payload: UnsubscribeRequest) -> dict[str, Any]:
    UNSUBSCRIBES.add(payload.journalist_email.lower())
    if payload.campaign_id and payload.campaign_id in CAMPAIGNS:
        campaign = CAMPAIGNS[payload.campaign_id]
        campaign['unsubscribe_count'] += 1
        campaign['report'].setdefault('unsubscribes', []).append(
            {
                'journalist_email': payload.journalist_email.lower(),
                'reason': payload.reason,
                'recorded_at': datetime.now(UTC).isoformat(),
            }
        )
    return {
        'ok': True,
        'journalist_email': payload.journalist_email.lower(),
        'campaign_id': payload.campaign_id,
        'reason': payload.reason,
        'unsubscribed': True,
    }
