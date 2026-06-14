import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from app.config import get_settings


async def send_email(to: str, subject: str, html_content: str) -> bool:
    """
    Delivery priority:
      1. Brevo API  — set BREVO_API_KEY in .env
      2. Gmail SMTP — set GMAIL_USER + GMAIL_APP_PASSWORD in .env
      3. Dev fallback — prints to console, returns False (triggers on-screen code)
    Returns True only when a real delivery succeeded.
    """
    settings = get_settings()

    # 1. Brevo
    if settings.brevo_api_key:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": settings.brevo_api_key, "Content-Type": "application/json"},
                    json={
                        "sender": {"name": settings.brevo_sender_name, "email": settings.brevo_sender_email},
                        "to": [{"email": to}],
                        "subject": subject,
                        "htmlContent": html_content,
                    },
                )
            if resp.is_success:
                return True
            print(f"[BREVO ERROR] {resp.status_code}: {resp.text} — trying Gmail SMTP fallback")
        except Exception as exc:
            print(f"[BREVO ERROR] {exc} — trying Gmail SMTP fallback")

    # 2. Gmail SMTP fallback
    if settings.gmail_user and settings.gmail_app_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.brevo_sender_name} <{settings.gmail_user}>"
            msg["To"] = to
            msg.attach(MIMEText(html_content, "html"))
            with smtplib.SMTP("smtp.gmail.com", 587) as s:
                s.starttls()
                s.login(settings.gmail_user, settings.gmail_app_password)
                s.send_message(msg)
            return True
        except Exception as exc:
            print(f"[GMAIL ERROR] {exc}")

    # 3. Dev fallback — show code on screen
    print(f"[EMAIL-DEV] To={to} | {subject}")
    print(html_content[:300])
    return False


async def send_verification_email(to: str, code: str) -> bool:
    return await send_email(
        to,
        "Your Anchor AI verification code",
        f"""<div style="font-family:sans-serif;max-width:480px;margin:auto">
  <h2 style="color:#0B1D35">Verify your email</h2>
  <p>Use the code below to complete your Anchor AI registration.</p>
  <div style="font-size:36px;font-weight:700;letter-spacing:10px;color:#0B1D35;margin:24px 0">{code}</div>
  <p style="color:#666;font-size:13px">Expires in 5 minutes. If you didn't request this, ignore this email.</p>
</div>""",
    )


async def send_password_reset_email(to: str, code: str) -> bool:
    return await send_email(
        to,
        "Reset your Anchor AI password",
        f"""<div style="font-family:sans-serif;max-width:480px;margin:auto">
  <h2 style="color:#0B1D35">Password reset</h2>
  <p>Use the code below to reset your Anchor AI password.</p>
  <div style="font-size:36px;font-weight:700;letter-spacing:10px;color:#0B1D35;margin:24px 0">{code}</div>
  <p style="color:#666;font-size:13px">Expires in 5 minutes. If you didn't request this, ignore this email.</p>
</div>""",
    )
