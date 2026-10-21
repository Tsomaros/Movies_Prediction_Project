"""Offline tests for the TMDB client, using a fake TMDB (httpx.MockTransport)."""

import asyncio
import time

import httpx
import pytest

from ml.data.tmdb_client import RateLimiter, TMDBClient, TMDBError


def make_client(handler, **kwargs) -> TMDBClient:
    """Client wired to a fake TMDB, fast by default (no throttle, no backoff)."""
    kwargs.setdefault("rate", 10_000)
    kwargs.setdefault("backoff_base", 0)
    return TMDBClient("test-token", transport=httpx.MockTransport(handler), **kwargs)


def sequence(*responses):
    """Handler returning the given responses in order, recording each request."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        item = responses[min(len(calls), len(responses)) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    return handler, calls


async def test_sends_bearer_token_and_params():
    handler, calls = sequence(httpx.Response(200, json={"id": 1}))
    async with make_client(handler) as client:
        data = await client.get("/movie/1", params={"append_to_response": "credits"})

    assert data == {"id": 1}
    assert calls[0].headers["Authorization"] == "Bearer test-token"
    assert calls[0].url.path == "/3/movie/1"
    assert calls[0].url.params["append_to_response"] == "credits"


async def test_404_returns_none_without_retry():
    handler, calls = sequence(httpx.Response(404))
    async with make_client(handler) as client:
        assert await client.get("/movie/999") is None
    assert len(calls) == 1


async def test_429_then_success_retries():
    handler, calls = sequence(
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"ok": True}),
    )
    async with make_client(handler) as client:
        assert await client.get("/movie/1") == {"ok": True}
    assert len(calls) == 2


async def test_5xx_retries():
    handler, calls = sequence(
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, json={"ok": True}),
    )
    async with make_client(handler) as client:
        assert await client.get("/movie/1") == {"ok": True}
    assert len(calls) == 3


async def test_network_error_retries():
    handler, calls = sequence(
        httpx.ConnectError("connection refused"),
        httpx.Response(200, json={"ok": True}),
    )
    async with make_client(handler) as client:
        assert await client.get("/movie/1") == {"ok": True}
    assert len(calls) == 2


async def test_gives_up_after_max_retries():
    handler, calls = sequence(httpx.Response(500))
    async with make_client(handler, max_retries=3) as client:
        with pytest.raises(TMDBError, match="3 attempts"):
            await client.get("/movie/1")
    assert len(calls) == 3


async def test_401_raises_without_retry():
    handler, calls = sequence(httpx.Response(401))
    async with make_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("/movie/1")
    assert len(calls) == 1


def test_retry_delay_honours_retry_after():
    client = make_client(lambda r: httpx.Response(200), backoff_base=1.0)
    response = httpx.Response(429, headers={"Retry-After": "3"})
    assert client.retry_delay(response, attempt=1) == 3.0


def test_retry_delay_backs_off_exponentially():
    client = make_client(lambda r: httpx.Response(200), backoff_base=1.0)
    # base * 2^(attempt-1) plus up to `base` of jitter
    assert 1.0 <= client.retry_delay(None, attempt=1) <= 2.0
    assert 4.0 <= client.retry_delay(None, attempt=3) <= 5.0
    assert client.retry_delay(None, attempt=20) == 60.0


async def test_rate_limiter_spaces_requests():
    limiter = RateLimiter(rate=50)  # one start every 20 ms
    start = time.monotonic()
    await asyncio.gather(*(limiter.wait() for _ in range(11)))
    # 11 starts need at least 10 intervals
    assert time.monotonic() - start >= 10 * 0.02 * 0.9


async def test_concurrency_cap():
    in_flight = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return httpx.Response(200, json={})

    async with make_client(handler, max_concurrency=3) as client:
        await asyncio.gather(*(client.get(f"/movie/{i}") for i in range(12)))
    assert peak == 3


def test_from_env_requires_token(monkeypatch):
    monkeypatch.setattr("ml.data.tmdb_client.load_dotenv", lambda: None)
    monkeypatch.delenv("TMDB_READ_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TMDB_READ_TOKEN"):
        TMDBClient.from_env()
