"""Redis pub/sub channel management for direct-message SSE fan-out.

Mirrors `feed_sse.py`. Only ciphertext payloads cross the channel — the server
never has plaintext, and SSE subscribers are gated to conversation participants.
"""
import json
import uuid
import asyncio
from typing import AsyncGenerator

CHANNEL = "dm:conversation:{conversation_id}"


async def publish_message(redis, conversation_id: uuid.UUID, payload: dict) -> None:
    channel = CHANNEL.format(conversation_id=conversation_id)
    await redis.publish(channel, json.dumps(payload))


async def subscribe_messages(redis, conversation_id: uuid.UUID) -> AsyncGenerator[str, None]:
    channel = CHANNEL.format(conversation_id=conversation_id)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
            if message and message.get("type") == "message":
                data = message.get("data", b"")
                if isinstance(data, bytes):
                    data = data.decode()
                yield data
            else:
                # Keepalive so the client connection isn't dropped.
                yield ": keepalive\n\n"
                await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
