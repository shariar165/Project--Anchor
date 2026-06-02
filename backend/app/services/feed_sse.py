"""Redis pub/sub channel management for Verification Feed SSE fan-out."""
import json
import uuid
import asyncio
from typing import AsyncGenerator

CHANNEL = "feed:signals:{post_id}"


async def publish_signal_update(redis, post_id: uuid.UUID, counts: dict) -> None:
    channel = CHANNEL.format(post_id=post_id)
    await redis.publish(channel, json.dumps(counts))


async def subscribe_signal_updates(redis, post_id: uuid.UUID) -> AsyncGenerator[str, None]:
    channel = CHANNEL.format(post_id=post_id)
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
                # Send keepalive comment every 30s so client doesn't disconnect
                yield ": keepalive\n\n"
                await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
