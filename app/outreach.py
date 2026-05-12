from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol
import asyncio
import smtplib
import ssl
import uuid

import httpx

from .config import Settings
from .models import ProductProfile


@dataclass
class DeliveryResult:
    provider: str
    message_id: str
    status: str


class EmailSender(Protocol):
    async def send(self, *, to_email: str, subject: str, text: str) -> DeliveryResult: ...


class ResendSender:
    def __init__(self, api_key: str, from_email: str, from_name: str) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    async def send(self, *, to_email: str, subject: str, text: str) -> DeliveryResult:
        payload = {
            "from": f"{self.from_name} <{self.from_email}>",
            "to": [to_email],
            "subject": subject,
            "text": text,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        return DeliveryResult(provider="resend", message_id=str(data.get("id", uuid.uuid4())), status="sent")


class SendGridSender:
    def __init__(self, api_key: str, from_email: str, from_name: str) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    async def send(self, *, to_email: str, subject: str, text: str) -> DeliveryResult:
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [{"type": "text/plain", "value": text}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        response.raise_for_status()
        message_id = response.headers.get("X-Message-Id", str(uuid.uuid4()))
        return DeliveryResult(provider="sendgrid", message_id=message_id, status="sent")


class SmtpSender:
    def __init__(self, *, host: str, port: int, username: str | None, password: str | None, use_tls: bool, use_ssl: bool, from_email: str, from_name: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.from_email = from_email
        self.from_name = from_name

    async def send(self, *, to_email: str, subject: str, text: str) -> DeliveryResult:
        def _send() -> str:
            msg = EmailMessage()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.set_content(text)
            context = ssl.create_default_context()
            if self.use_ssl:
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as smtp:
                    if self.username and self.password:
                        smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port) as smtp:
                    if self.use_tls:
                        smtp.starttls(context=context)
                    if self.username and self.password:
                        smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            return str(uuid.uuid4())

        message_id = await asyncio.to_thread(_send)
        return DeliveryResult(provider="smtp", message_id=message_id, status="sent")


class ConsoleSender:
    async def send(self, *, to_email: str, subject: str, text: str) -> DeliveryResult:
        message_id = str(uuid.uuid4())
        print(f"[dry-console-send] to={to_email} subject={subject}\n{text}\n")
        return DeliveryResult(provider="console", message_id=message_id, status="sent")


def build_sender(settings: Settings) -> EmailSender:
    if settings.email_provider == "resend" and settings.resend_api_key:
        return ResendSender(settings.resend_api_key, settings.outreach_from_email, settings.outreach_from_name)
    if settings.email_provider == "sendgrid" and settings.sendgrid_api_key:
        return SendGridSender(settings.sendgrid_api_key, settings.outreach_from_email, settings.outreach_from_name)
    if settings.email_provider == "smtp" and settings.smtp_host:
        return SmtpSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            use_ssl=settings.smtp_use_ssl,
            from_email=settings.outreach_from_email,
            from_name=settings.outreach_from_name,
        )
    if settings.allow_console_sender:
        return ConsoleSender()
    raise RuntimeError("No email provider configured. Set RESEND_API_KEY, SENDGRID_API_KEY, or SMTP_HOST, or enable ALLOW_CONSOLE_SENDER for dry-run execution.")


def pitch_subject(product: ProductProfile, outlet: str) -> str:
    return f"Pitch: {product.product_name} for {outlet}"


def followup_subject(product: ProductProfile, outlet: str) -> str:
    return f"Follow-up: {product.product_name} for {outlet}"


def build_pitch_text(product: ProductProfile, journalist_name: str, rationale: list[str], quote: dict[str, str | int]) -> str:
    bullets = "\n".join(f"- {item}" for item in rationale[:4])
    angle = product.launch_angle or f"{product.category} launch"
    return (
        f"Hi {journalist_name},\n\n"
        f"I’m reaching out about {product.product_name} from {product.company_name}. "
        f"The angle is {angle}.\n\n"
        f"Why this looks like a fit:\n{bullets}\n\n"
        f"Product summary: {product.description}\n"
        f"Website: {product.website or 'n/a'}\n"
        f"Media kit: {product.media_kit_url or 'n/a'}\n\n"
        f"x402 pricing: {quote['price_per_pitch_usdc']} USDC per pitch, total {quote['total_usdc']} USDC for this campaign.\n\n"
        f"Best,\n{product.contact_name or product.company_name}\n{product.contact_email}"
    )


def build_followup_text(product: ProductProfile, journalist_name: str, rationale: list[str]) -> str:
    bullets = "\n".join(f"- {item}" for item in rationale[:3])
    return (
        f"Hi {journalist_name},\n\n"
        f"Just following up on the note about {product.product_name}. I thought it might still be relevant because:\n{bullets}\n\n"
        f"If you'd like a tighter angle or more context, I’m happy to send it.\n\n"
        f"Best,\n{product.contact_name or product.company_name}\n{product.contact_email}"
    )
