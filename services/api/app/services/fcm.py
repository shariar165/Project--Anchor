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


async def send_to_token(
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> str | None:
    """
    Send a single high-priority push notification to one FCM token.
    Returns the FCM message_id on success, None on failure or if unconfigured.
    """
    app = _get_app()
    if app is None:
        logger.debug("[FCM] send_to_token skipped (FCM unconfigured) to %.20s…", token)
        return None
    try:
        from firebase_admin import messaging
        from app.config import get_settings

        settings = get_settings()
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                ttl=settings.fcm_default_ttl_seconds,
            ),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", content_available=True),
                ),
            ),
        )
        loop = asyncio.get_event_loop()
        message_id: str = await loop.run_in_executor(None, messaging.send, msg)
        return message_id
    except Exception as exc:
        logger.warning("[FCM] send_to_token failed: %s", exc)
        return None


async def send_batch(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> dict[str, str | None]:
    """
    Send to multiple tokens (up to 500 per call per FCM limits).
    Returns {token: message_id | None} mapping.
    """
    if not tokens:
        return {}

    app = _get_app()
    if app is None:
        logger.debug("[FCM] send_batch skipped (FCM unconfigured) — %d tokens", len(tokens))
        return {t: None for t in tokens}

    results: dict[str, str | None] = {}
    try:
        from firebase_admin import messaging
        from app.config import get_settings

        settings = get_settings()
        # FCM batch limit is 500
        chunk_size = min(500, settings.fcm_default_ttl_seconds and 500)
        for i in range(0, len(tokens), 500):
            chunk = tokens[i : i + 500]
            multicast_msg = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=chunk,
                android=messaging.AndroidConfig(
                    priority="high",
                    ttl=settings.fcm_default_ttl_seconds,
                ),
            )
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, messaging.send_each_for_multicast, multicast_msg
            )
            for j, send_resp in enumerate(resp.responses):
                results[chunk[j]] = send_resp.message_id if send_resp.success else None
    except Exception as exc:
        logger.warning("[FCM] send_batch failed: %s", exc)
        for t in tokens:
            results.setdefault(t, None)

    return results
