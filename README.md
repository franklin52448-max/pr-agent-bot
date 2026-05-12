# pr-agent-bot

A FastAPI public-relations automation service that pitches products to journalists instead of evaluating pull requests.

## What it does

- Matches product launches to a mock database of roughly 2,000 journalists across AI, DeFi, fintech, cybersecurity, climate, consumer tech, health tech, and developer tools.
- Sends actual outbound email via Resend, SendGrid, or SMTP when configured.
- Supports dry-run mode so you can preview who would be contacted without sending.
- Runs background workers for weekly journalist refreshes and 3-day follow-ups when no response is tracked.
- Exposes REST endpoints for campaign registration, status, and match previews.
- Includes x402 pricing at $0.50 USDC per pitch.

## API

### POST /register
Create a campaign from product details.

Request body:

```json
{
  "product": {
    "product_name": "Acme AI Copilot",
    "company_name": "Acme Labs",
    "description": "A launch-ready AI assistant for enterprise workflows.",
    "category": "ai",
    "keywords": ["llm", "automation", "workflow"],
    "target_beats": ["ai"],
    "target_regions": ["north america"],
    "target_outlets": ["Signal AI 1"],
    "launch_angle": "new product launch",
    "contact_name": "Franklin",
    "contact_email": "franklin@example.com",
    "website": "https://example.com",
    "media_kit_url": "https://example.com/press",
    "notes": "optional"
  },
  "dry_run": true,
  "max_journalists": 12
}
```

### GET /status?campaign_id=...
Returns campaign state, pitch delivery status, and follow-up state.

### POST /match-preview
Returns ranked journalist matches without creating a campaign.

## Environment variables

Email delivery:

- `EMAIL_PROVIDER=resend|sendgrid|smtp`
- `RESEND_API_KEY`
- `SENDGRID_API_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`
- `OUTREACH_FROM_EMAIL`
- `OUTREACH_FROM_NAME`
- `ALLOW_CONSOLE_SENDER=true` for local dry-run console delivery

Workers and pricing:

- `X402_PRICE_USDC=0.50`
- `DEFAULT_MATCH_LIMIT=12`
- `FOLLOW_UP_AFTER_DAYS=3`
- `WEEKLY_UPDATE_POLL_SECONDS=3600`
- `FOLLOW_UP_POLL_SECONDS=60`
- `DRY_RUN_DEFAULT=true`

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Notes

- The seed journalist database is synthetic and generated at startup.
- x402 pricing is reflected in every match preview and registration response.
- The service is built to pitch products to journalists, not to manage code review or pull requests.
