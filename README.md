# Zero-human PR agent

BTNOMB idea_006: a FastAPI service that evaluates pull requests, decides when to auto-approve, when to escalate, and when to initiate journalist outreach.

## What it does

- Scores pull requests with a deterministic rubric.
- Produces an outreach brief for journalists when the PR is newsworthy.
- Supports x402-style payment gating in USDC (ERC-20) for premium analysis routes.
- Exposes a small API that can be embedded into internal tooling or a bot workflow.

## Stack

- Python 3.11+
- FastAPI
- Pydantic
- Uvicorn
- Optional Web3 support for on-chain verification of USDC payments

## Environment

Set these variables when running against a live chain/payment flow:

- `APP_NAME` – service name shown in responses
- `ADMIN_EMAIL` – optional contact address
- `X402_CHAIN_ID` – EVM chain id used for the payment flow
- `X402_RPC_URL` – RPC endpoint used for transaction verification
- `X402_TREASURY_ADDRESS` – receiving wallet address
- `X402_USDC_CONTRACT` – USDC ERC-20 contract address for the chain
- `X402_MIN_AMOUNT_USDC` – minimum USDC payment required for premium routes
- `X402_REQUIRED_CONFIRMATIONS` – confirmation depth for settlement checks
- `X402_PRICE_USDC` – default fee in USDC for premium actions

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API

### GET /health
Basic liveness probe.

### POST /v1/prs/evaluate
Scores a pull request and returns a decision.

### POST /v1/prs/brief
Builds a journalist-facing pitch from the PR metadata.

### POST /v1/outreach/journalists
Ranks a journalist list against a PR and returns outreach recommendations.

### POST /v1/payments/x402/quote
Returns a USDC payment quote for premium analysis.

### POST /v1/payments/x402/verify
Verifies an x402 payment payload against the configured treasury and token settings.

## Notes on x402 + USDC

This repository includes a practical payment layer that expects a USDC ERC-20 transfer or authorization payload that can be validated against chain data. The app does not hard-code a single provider; instead, it accepts a signed payment envelope and verifies the token contract, recipient, amount, chain id, and settlement status before allowing premium execution.

## Scoring rubric

The PR score blends:

- novelty
- user impact
- technical clarity
- evidence quality
- release readiness
- communication readiness for external outreach
- risk / compliance penalties

The score maps to:

- `0-39` → reject / needs work
- `40-69` → improve and resubmit
- `70-84` → good candidate for human review
- `85-100` → strong autonomous candidate

## Project layout

- `app/main.py` – FastAPI app and routes
- `app/config.py` – settings and pricing config
- `app/models.py` – request/response schemas
- `app/scoring.py` – deterministic score engine
- `app/outreach.py` – journalist outreach generation and ranking
- `app/payments.py` – x402 USDC payment verification and quotes

## License

MIT
