from __future__ import annotations

import time

from typing import Any


def consume_fixed_window(*, redis_client: Any, namespace: str, subject: str, limit: int) -> bool:
    """Consume one token in a Redis-backed one-minute fixed window."""
    if limit <= 0:
        return True

    window = int(time.time() // 60)
    key = f"relayops:rate-limit:{namespace}:{subject}:{window}"
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, 70)
    count, _ = pipe.execute()
    return int(count) <= limit
