"""
Firebase Cloud Messaging service.

Initializes lazily on first use. Degrades gracefully (logs a warning and
returns None/empty results) when:
  - firebase-admin is not installed
  - FCM_SERVICE_ACCOUNT_JSON_PATH is not configured
  - The service-account file does not exist or is invalid
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_firebase_app = None
_init_attempted = False


def _get_app():
    global _firebase_app, _init_attempted
    if _init_attempted:
        return _firebase_app
    _init_attempted = True
    try:
        import firebase_admin
        from firebase_admin import credentials
        from app.config import get_settings

        settings = get_settings()
        if settings.fcm_service_account_json:
            import json
            cred = credentials.Certificate(json.loads(settings.fcm_service_account_json))
        elif settings.fcm_service_account_json_path:
            cred = credentials.Certificate(settings.fcm_service_account_json_path)
        else:
            logger.warning("[FCM] FCM not configured — push disabled")
            return None
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("[FCM] Firebase app initialized for project %s", settings.fcm_project_id)
        return _firebase_app
    except ImportError:
        logger.warning("[FCM] firebase-admin not installed — push disabled")
        return None
    except Exception as exc:
        logger.warning("[FCM] Firebase init failed: %s — push disabled", exc)
        return None


# Result shape returned by send_to_token / send_batch.
#   {"message_id": str | None, "ok": bool, "error": str | None}
# `error` is a stable category string from _classify(): one of
#   "unregistered" | "sender_id_mismatch" | "invalid_argument" | "auth"
#   | "unavailable" | "unconfigured" | "error". Callers use it to decide
# whether a token is permanently invalid (and should be disabled).
SendResult = dict


# Permanently-invalid categories: the token will never work again and the
# caller should disable it.
PERMANENT_ERRORS = frozenset({"unregistered", "sender_id_mismatch", "invalid_argument"})


def _classify(exc: Exception) -> str:
    """Map a firebase-admin send exception to a stable category string."""
    name = type(exc).__name__
    by_name = {
        "UnregisteredError": "unregistered",
        "SenderIdMismatchError": "sender_id_mismatch",
        "InvalidArgumentError": "invalid_argument",
        "UnauthenticatedError": "auth",
        "PermissionDeniedError": "auth",
        "ThirdPartyAuthError": "auth",
        "UnavailableError": "unavailable",
        "InternalError": "unavailable",
        "QuotaExceededError": "unavailable",
    }
    if name in by_name:
        return by_name[name]
    # Fall back to message inspection (covers wrapped/transport errors).
    s = str(exc).lower()
    if "not a valid fcm registration token" in s or "requested entity was not found" in s \
            or "unregistered" in s or "not found" in s:
        return "unregistered"
    if "senderid mismatch" in s or "sender id mismatch" in s:
        return "sender_id_mismatch"
    if "permission" in s and "denied" in s:
        return "auth"
    return "error"


def _result(message_id: str | None = None, error: str | None = None) -> SendResult:
    return {"message_id": message_id, "ok": message_id is not None, "error": error}


def _message(token: str, title: str, body: str, data: dict[str, str] | None, ttl: int):
    from firebase_admin import messaging
    return messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=token,
        android=messaging.AndroidConfig(priority="high", ttl=ttl),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", content_available=True),
            ),
        ),
        webpush=messaging.WebpushConfig(
            notification=messaging.WebpushNotification(title=title, body=body),
        ),
    )


async def send_to_token(
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> SendResult:
    """
    Send a single high-priority push notification to one FCM token.
    Returns a SendResult: {"message_id", "ok", "error"}.
    """
    app = _get_app()
    if app is None:
        logger.debug("[FCM] send_to_token skipped (FCM unconfigured) to %.20s…", token)
        return _result(error="unconfigured")
    try:
        from firebase_admin import messaging
        from app.config import get_settings

        settings = get_settings()
        msg = _message(token, title, body, data, settings.fcm_default_ttl_seconds)
        loop = asyncio.get_event_loop()
        message_id: str = await loop.run_in_executor(None, messaging.send, msg)
        return _result(message_id=message_id)
    except Exception as exc:
        category = _classify(exc)
        logger.warning("[FCM] send_to_token failed (%s): %s", category, exc)
        return _result(error=category)


async def send_batch(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> dict[str, SendResult]:
    """
    Send to multiple tokens (chunked at the 500/token FCM limit).
    Returns {token: SendResult}. Each SendResult carries an `error` category so
    callers can disable permanently-invalid tokens (see PERMANENT_ERRORS).
    """
    if not tokens:
        return {}

    app = _get_app()
    if app is None:
        logger.debug("[FCM] send_batch skipped (FCM unconfigured) — %d tokens", len(tokens))
        return {t: _result(error="unconfigured") for t in tokens}

    results: dict[str, SendResult] = {}
    try:
        from firebase_admin import messaging
        from app.config import get_settings

        settings = get_settings()
        ttl = settings.fcm_default_ttl_seconds
        for i in range(0, len(tokens), 500):
            chunk = tokens[i : i + 500]
            multicast_msg = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=chunk,
                android=messaging.AndroidConfig(priority="high", ttl=ttl),
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(title=title, body=body),
                ),
            )
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, messaging.send_each_for_multicast, multicast_msg
            )
            for j, send_resp in enumerate(resp.responses):
                if send_resp.success:
                    results[chunk[j]] = _result(message_id=send_resp.message_id)
                else:
                    results[chunk[j]] = _result(error=_classify(send_resp.exception))
    except Exception as exc:
        category = _classify(exc)
        logger.warning("[FCM] send_batch failed (%s): %s", category, exc)
        for t in tokens:
            results.setdefault(t, _result(error=category))

    return results
