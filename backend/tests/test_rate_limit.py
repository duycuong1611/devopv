from app.rate_limit import consume_fixed_window


class FakePipeline:
    def __init__(self, owner):
        self.owner = owner
        self.key = ""

    def incr(self, key):
        self.key = key
        self.owner.counts[key] = self.owner.counts.get(key, 0) + 1
        return self

    def expire(self, key, seconds):
        return self

    def execute(self):
        return [self.owner.counts[self.key], True]


class FakeRedis:
    def __init__(self):
        self.counts = {}

    def pipeline(self):
        return FakePipeline(self)


def test_fixed_window_rejects_after_limit(monkeypatch) -> None:
    monkeypatch.setattr("app.rate_limit.time.time", lambda: 120.0)
    client = FakeRedis()

    assert consume_fixed_window(redis_client=client, namespace="test", subject="a", limit=2)
    assert consume_fixed_window(redis_client=client, namespace="test", subject="a", limit=2)
    assert not consume_fixed_window(redis_client=client, namespace="test", subject="a", limit=2)
