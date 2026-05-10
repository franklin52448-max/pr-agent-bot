from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .config import settings
from .models import X402QuoteRequest, X402QuoteResponse, X402VerifyRequest, X402VerifyResponse

try:
    from web3 import Web3
    from web3.contract import Contract
except Exception:  # pragma: no cover - optional dependency path
    Web3 = None  # type: ignore[assignment]
    Contract = Any  # type: ignore[assignment]


USDC_DECIMALS = 6
USDC_SYMBOL = 'USDC'
ERC20_TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'


@dataclass(frozen=True)
class PaymentCheck:
    ok: bool
    reason: str
    details: dict[str, Any]


def quote_payment(request: X402QuoteRequest) -> X402QuoteResponse:
    amount = request.price_usdc if request.price_usdc is not None else settings.x402_price_usdc
    amount = max(amount, settings.x402_min_amount_usdc)
    return X402QuoteResponse(
        route=request.route,
        amount_usdc=round(amount, 6),
        chain_id=settings.x402_chain_id,
        token=settings.x402_usdc_contract,
        treasury=settings.x402_treasury_address,
        memo=request.purpose,
    )


def verify_payment(request: X402VerifyRequest) -> X402VerifyResponse:
    checks = [
        _check_chain(request.payment.chain_id),
        _check_token(request.payment.token_address),
        _check_treasury(request.payment.treasury_address),
        _check_amount(request.payment.amount_usdc),
    ]
    for check in checks:
        if not check.ok:
            return X402VerifyResponse(
                ok=False,
                reason=check.reason,
                accepted=False,
                details=check.details,
            )

    if request.payment.settlement_status == 'failed':
        return X402VerifyResponse(ok=False, reason='payment marked failed', accepted=False, details={})

    if request.payment.settlement_status == 'settled':
        return X402VerifyResponse(ok=True, reason='payment settled', accepted=True, details={'route': request.route})

    on_chain = _verify_on_chain(request.payment.tx_hash, request.payment.amount_usdc)
    if on_chain.ok:
        return X402VerifyResponse(ok=True, reason=on_chain.reason, accepted=True, details=on_chain.details)

    return X402VerifyResponse(
        ok=False,
        reason=on_chain.reason or 'payment pending',
        accepted=False,
        details=on_chain.details,
    )


def _check_chain(chain_id: int) -> PaymentCheck:
    if chain_id != settings.x402_chain_id:
        return PaymentCheck(False, 'unexpected chain id', {'expected': settings.x402_chain_id, 'received': chain_id})
    return PaymentCheck(True, 'chain ok', {'chain_id': chain_id})


def _check_token(token_address: str) -> PaymentCheck:
    if token_address.lower() != settings.x402_usdc_contract.lower():
        return PaymentCheck(False, 'unexpected token contract', {'expected': settings.x402_usdc_contract, 'received': token_address})
    return PaymentCheck(True, 'token ok', {'token_address': token_address})


def _check_treasury(treasury_address: str) -> PaymentCheck:
    if treasury_address.lower() != settings.x402_treasury_address.lower():
        return PaymentCheck(False, 'unexpected treasury address', {'expected': settings.x402_treasury_address, 'received': treasury_address})
    return PaymentCheck(True, 'treasury ok', {'treasury_address': treasury_address})


def _check_amount(amount_usdc: float) -> PaymentCheck:
    required = settings.x402_min_amount_usdc
    if amount_usdc + 1e-9 < required:
        return PaymentCheck(False, 'payment amount too low', {'required': required, 'received': amount_usdc})
    return PaymentCheck(True, 'amount ok', {'amount_usdc': round(amount_usdc, 6)})


def _verify_on_chain(tx_hash: str | None, amount_usdc: float) -> PaymentCheck:
    if not tx_hash:
        return PaymentCheck(False, 'payment pending and no transaction hash provided', {})
    if Web3 is None or not settings.x402_rpc_url:
        return PaymentCheck(True, 'transaction envelope accepted without rpc verification', {'tx_hash': tx_hash, 'amount_usdc': amount_usdc})

    web3 = Web3(Web3.HTTPProvider(settings.x402_rpc_url))
    if not web3.is_connected():
        return PaymentCheck(False, 'could not connect to rpc', {'tx_hash': tx_hash})

    receipt = web3.eth.get_transaction_receipt(tx_hash)
    latest_block = web3.eth.block_number
    confirmations = max(0, latest_block - receipt.blockNumber + 1)
    if confirmations < settings.x402_required_confirmations:
        return PaymentCheck(False, 'insufficient confirmations', {'confirmations': confirmations, 'required': settings.x402_required_confirmations})

    token_contract = _usdc_contract(web3)
    events = token_contract.events.Transfer().process_receipt(receipt)
    treasury = settings.x402_treasury_address.lower()
    target_wei = int(math.floor(amount_usdc * (10 ** USDC_DECIMALS)))
    for event in events:
        args = event['args']
        if str(args['to']).lower() == treasury and int(args['value']) >= target_wei:
            return PaymentCheck(
                True,
                'on-chain usdc transfer confirmed',
                {
                    'tx_hash': tx_hash,
                    'confirmations': confirmations,
                    'value_raw': int(args['value']),
                    'token': settings.x402_usdc_contract,
                },
            )

    return PaymentCheck(False, 'no qualifying usdc transfer found', {'tx_hash': tx_hash, 'confirmations': confirmations})


def _usdc_contract(web3):
    abi = [
        {
            'anonymous': False,
            'inputs': [
                {'indexed': True, 'internalType': 'address', 'name': 'from', 'type': 'address'},
                {'indexed': True, 'internalType': 'address', 'name': 'to', 'type': 'address'},
                {'indexed': False, 'internalType': 'uint256', 'name': 'value', 'type': 'uint256'},
            ],
            'name': 'Transfer',
            'type': 'event',
        }
    ]
    return web3.eth.contract(address=Web3.to_checksum_address(settings.x402_usdc_contract), abi=abi)
