import json

import httpx
import pytest
from openai import OpenAI

from safescale.retrieval.embedder import (
    DIMENSIONS,
    OpenAIEmbedder,
    batches,
    estimate_tokens,
)


def test_batches_respect_item_limit():
    sizes = [len(b) for b in batches(["x"] * 600, max_items=256)]
    assert sizes == [256, 256, 88]


def test_batches_respect_token_budget():
    texts = ["a" * 3000] * 10  # ~1,001 estimated tokens each
    result = list(batches(texts, max_tokens=2500))
    assert [len(b) for b in result] == [2, 2, 2, 2, 2]
    assert all(sum(estimate_tokens(t) for t in b) <= 2500 for b in result)


def test_batches_keep_order_and_oversized_items():
    texts = ["short", "x" * 10_000, "end"]
    assert [t for b in batches(texts, max_tokens=100) for t in b] == texts


def mock_openai(requests: list[dict], dims: int = DIMENSIONS, shuffle: bool = True) -> OpenAI:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        data = [
            {"object": "embedding", "index": i, "embedding": [float(i)] * dims}
            for i in range(len(body["input"]))
        ]
        if shuffle:
            data.reverse()  # the API does not promise order; we must sort by index
        usage = {"prompt_tokens": 7, "total_tokens": 7}
        return httpx.Response(
            200, json={"object": "list", "data": data, "model": body["model"], "usage": usage}
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAI(api_key="test-key", http_client=http, max_retries=0)


def test_openai_embedder_sends_model_and_preserves_order():
    requests: list[dict] = []
    embedder = OpenAIEmbedder(client=mock_openai(requests), model="text-embedding-3-small")
    vectors = embedder.embed(["a", "b", "c"])
    assert requests[0]["model"] == "text-embedding-3-small"
    assert requests[0]["input"] == ["a", "b", "c"]
    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]
    assert embedder.total_tokens == 7


def test_openai_embedder_rejects_wrong_dimensions():
    embedder = OpenAIEmbedder(client=mock_openai([], dims=3))
    with pytest.raises(RuntimeError, match="dimensions"):
        embedder.embed(["a"])


@pytest.mark.live
def test_live_openai_embedding():
    from safescale import config

    config.load_dotenv()
    embedder = OpenAIEmbedder()
    [vector] = embedder.embed(["lithium-ion battery overheating"])
    assert len(vector) == DIMENSIONS
    assert embedder.total_tokens > 0
