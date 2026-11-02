"""Out-of-band notifications for price alerts (issue #65).

Two opt-in channels, both stdlib-only (no new dependencies):
- SMTP email: set ALERT_SMTP_HOST (+ optional user/pass/from/to). Off when unset.
- Webhook: POST JSON to ALERT_WEBHOOK_URL (e.g. ntfy, Gotify, Slack webhook).
  Off when unset.

When both are unset, notify_* are no-ops returning False (in-app banner
remains the primary surface). Never raises: failures are logged.
"""

from __future__ import annotations

import json
import logging
import smtplib
import urllib.parse
import urllib.request
from base64 import urlsafe_b64encode
from email.message import EmailMessage

from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select

from reign.config import settings
from reign.domain.models import PushSubscription

try:
    from pywebpush import WebPushException, webpush

    WEBPUSH_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    WebPushException = Exception  # type: ignore[assignment,misc]
    webpush = None  # type: ignore[assignment]
    WEBPUSH_AVAILABLE = False

logger = logging.getLogger("reign.notify")

HTTP_OK_MIN = 200
HTTP_OK_MAX = 300


def smtp_configured() -> bool:
    return bool(getattr(settings, "alert_smtp_host", ""))


def webhook_configured() -> bool:
    return bool(getattr(settings, "alert_webhook_url", ""))


def notify_email(subject: str, body: str, timeout_s: int = 10) -> bool:
    """Send an email via configured SMTP. Returns True if attempted+sent."""
    host = getattr(settings, "alert_smtp_host", "")
    if not host:
        return False
    port = int(getattr(settings, "alert_smtp_port", 587) or 587)
    username = getattr(settings, "alert_smtp_user", "") or ""
    password = getattr(settings, "alert_smtp_password", "") or ""
    sender = getattr(settings, "alert_email_from", "") or username or "reign@localhost"
    to = getattr(settings, "alert_email_to", "") or username
    if not to:
        logger.warning("Alert email skipped: no recipient configured")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=timeout_s) as client:
            client.starttls()
            if username:
                client.login(username, password)
            client.send_message(msg)
        return True
    except Exception as e:
        logger.warning("Alert email failed: %s", e)
        return False


def notify_webhook(title: str, body: str, extra: dict | None = None, timeout_s: int = 10) -> bool:
    """POST a JSON payload to the configured webhook URL (http/https only)."""
    url = getattr(settings, "alert_webhook_url", "")
    if not url:
        return False
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        logger.warning("Alert webhook skipped: URL must be http(s)")
        return False
    payload = {"title": title, "message": body, **(extra or {})}
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        opener = urllib.request.urlopen
        with opener(req, timeout=timeout_s) as resp:
            return HTTP_OK_MIN <= resp.status < HTTP_OK_MAX
    except Exception as e:
        logger.warning("Alert webhook failed: %s", e)
        return False


def notify_alert_fired(
    symbol: str, direction: str, price: object, target: object, holding_id: int
) -> dict:
    """Fan out one alert to all configured channels. Never raises."""
    arrow = ">=" if direction == "above" else "<="
    title = f"Reign alert: {symbol} {arrow} {target}"
    body = f"{symbol} hit {price} ({direction} target {target}, holding #{holding_id})."
    extra = {"symbol": symbol, "direction": direction, "holding_id": holding_id}
    return {
        "email": notify_email(title, body),
        "webhook": notify_webhook(title, body, extra),
    }


def vapid_configured() -> bool:
    return bool(
        getattr(settings, "vapid_private_key", "") and getattr(settings, "vapid_public_key", "")
    )


def generate_vapid_keys() -> tuple[str, str]:
    """Generate a VAPID ES256 keypair, base64url raw (public 65B, private 32B)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_numbers = private_key.public_key().public_numbers()
    x = public_numbers.x.to_bytes(32, "big")
    y = public_numbers.y.to_bytes(32, "big")
    priv = private_key.private_numbers().private_value.to_bytes(32, "big")
    return _b64raw(b"\x04" + x + y), _b64raw(priv)


def _b64raw(raw: bytes) -> str:
    """base64url without padding (Web Push key format)."""
    return urlsafe_b64encode(raw).decode().rstrip("=")


def send_webpush(endpoint: str, p256dh: str, auth: str, title: str, body: str) -> bool:
    """Send one Web Push message. Returns True on success. Never raises."""
    if not vapid_configured() or not WEBPUSH_AVAILABLE or webpush is None:
        if vapid_configured() and not WEBPUSH_AVAILABLE:
            logger.warning("Web Push skipped: pywebpush not installed")
        return False
    try:
        webpush(
            subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=getattr(settings, "vapid_private_key", ""),
            vapid_claims={"sub": getattr(settings, "vapid_subject", "mailto:reign@localhost")},
        )
        return True
    except WebPushException as e:
        logger.warning("Web Push failed: %s", e)
        return False
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Web Push failed: %s", e)
        return False


async def send_push_alerts(session, title: str, body: str) -> int:
    """Send a push to every subscription in this profile. Returns sent count."""
    if not vapid_configured():
        return 0
    try:
        rows = (await session.execute(select(PushSubscription))).scalars().all()
    except Exception as e:
        logger.warning("Web Push skipped: %s", e)
        return 0
    sent = 0
    for sub in rows:
        if send_webpush(sub.endpoint, sub.p256dh, sub.auth, title, body):
            sent += 1
    return sent
