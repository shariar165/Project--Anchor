import httpx
from app.config import get_settings


async def send_sms(phone: str, message: str) -> bool:
    settings = get_settings()
    if not settings.sms_api_url:
        print(f"[SMS-DEV] To={phone} | {message}")
        return False  # console fallback — not a real delivery
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                settings.sms_api_url,
                json={"api_key": settings.sms_api_key, "sender_id": settings.sms_sender_id,
                      "to": phone, "message": message},
            )
            resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[SMS ERROR] {exc}")
        return False


async def send_otp_sms(phone: str, code: str) -> bool:
    return await send_sms(phone, f"Your Anchor AI code: {code}. Valid for 5 minutes. Do not share.")
