"""
Provider-independent Email Provider System for Clinica.

Supports:
- Resend (Production REST API)
- SMTP (Standard SMTP/STARTTLS)
- Mock / Console (Local dev / testing)
"""
import abc
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple
import httpx

from app.config import settings
from app.logger import log_event

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"

try:
    import resend
    HAS_RESEND_SDK = True
except ImportError:
    HAS_RESEND_SDK = False

class BaseEmailProvider(abc.ABC):
    """Abstract email provider interface."""

    @abc.abstractmethod
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Send an email message.
        Returns: (success: bool, error_message: Optional[str])
        """
        pass

class ResendEmailProvider(BaseEmailProvider):
    """
    Resend API Email Provider.
    Sends transactional emails via Resend SDK or REST API.
    """

    def __init__(self, api_key: Optional[str] = None, from_email: Optional[str] = None):
        self.api_key = api_key or settings.RESEND_API_KEY
        self.from_email = from_email or settings.NOTIFICATION_FROM_EMAIL or "onboarding@resend.dev"

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not settings.NOTIFICATION_ENABLED:
            logger.debug(f"[Resend] Notification skipped (NOTIFICATION_ENABLED=False): {subject}")
            return True, None

        if not self.api_key:
            logger.warning(
                f"[Resend] RESEND_API_KEY is not configured. Simulating email to {to_email}: '{subject}'"
            )
            log_event("EMAIL_SENT_SIMULATED", {"provider": "resend", "to": to_email, "subject": subject})
            return True, None

        html_content = (
            html_body
            if html_body
            else f"<div style='font-family:sans-serif;line-height:1.6;color:#333;'><pre style='white-space:pre-wrap;font-family:sans-serif;'>{body}</pre></div>"
        )

        if HAS_RESEND_SDK:
            try:
                resend.api_key = self.api_key
                params = {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                    "html": html_content,
                }
                res = resend.Emails.send(params)
                email_id = res.get("id") if isinstance(res, dict) else getattr(res, "id", str(res))
                logger.info(f"[Resend] Email successfully sent to {to_email} (ID: {email_id})")
                log_event("EMAIL_SENT", {"provider": "resend", "to": to_email, "subject": subject, "email_id": email_id})
                return True, None
            except Exception as exc:
                error_msg = f"Resend SDK error: {str(exc)}"
                logger.error(f"[Resend] {error_msg}")
                log_event("EMAIL_FAILED", {"provider": "resend", "to": to_email, "subject": subject, "error": error_msg})
                return False, error_msg

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "text": body,
            "html": html_content,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(RESEND_API_URL, headers=headers, json=payload)
                if res.status_code in (200, 201):
                    res_data = res.json()
                    email_id = res_data.get("id")
                    logger.info(f"[Resend] Email successfully sent to {to_email} (ID: {email_id})")
                    log_event("EMAIL_SENT", {"provider": "resend", "to": to_email, "subject": subject, "email_id": email_id})
                    return True, None

                try:
                    err_json = res.json()
                    error_msg = err_json.get("message") or str(err_json)
                except Exception:
                    error_msg = res.text

                full_error = f"Resend API error ({res.status_code}): {error_msg}"
                logger.error(f"[Resend] {full_error}")
                log_event("EMAIL_FAILED", {"provider": "resend", "to": to_email, "subject": subject, "error": full_error})
                return False, full_error

        except httpx.HTTPError as exc:
            error_msg = f"Resend HTTP request failed: {str(exc)}"
            logger.error(f"[Resend] {error_msg}")
            log_event("EMAIL_FAILED", {"provider": "resend", "to": to_email, "subject": subject, "error": error_msg})
            return False, error_msg
        except Exception as exc:
            error_msg = f"Unexpected error sending email via Resend: {str(exc)}"
            logger.error(f"[Resend] {error_msg}")
            log_event("EMAIL_FAILED", {"provider": "resend", "to": to_email, "subject": subject, "error": error_msg})
            return False, error_msg

class SMTPEmailProvider(BaseEmailProvider):
    """
    Standard SMTP Email Provider.
    """

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not settings.NOTIFICATION_ENABLED or not settings.SMTP_HOST:
            logger.debug(f"[SMTP] Notification skipped: {subject}")
            return True, None

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.NOTIFICATION_FROM_EMAIL
            msg["To"] = to_email
            msg.attach(MIMEText(body, "plain"))
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.NOTIFICATION_FROM_EMAIL, [to_email], msg.as_string())

            log_event("EMAIL_SENT", {"provider": "smtp", "to": to_email, "subject": subject})
            return True, None

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"[SMTP] Email send failed to {to_email}: {error_msg}")
            log_event("EMAIL_FAILED", {"provider": "smtp", "to": to_email, "subject": subject, "error": error_msg})
            return False, error_msg

class MockEmailProvider(BaseEmailProvider):
    """
    Mock Email Provider for local development & testing.
    """

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        logger.info(f"[MockEmail] To: {to_email} | Subject: {subject}\nBody: {body[:100]}...")
        log_event("EMAIL_SENT_MOCK", {"provider": "mock", "to": to_email, "subject": subject})
        return True, None

def get_email_provider() -> BaseEmailProvider:
    """
    Factory to instantiate the configured email provider.
    """
    provider_name = (settings.EMAIL_PROVIDER or "resend").strip().lower()

    if provider_name == "resend":
        return ResendEmailProvider()
    elif provider_name == "smtp":
        return SMTPEmailProvider()
    elif provider_name in ("mock", "console", "none"):
        return MockEmailProvider()

    return ResendEmailProvider()
