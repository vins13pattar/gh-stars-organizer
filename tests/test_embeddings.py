import httpx

from gh_stars_organizer.embeddings import EmbeddingClient


def test_embedding_client_api_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    client = EmbeddingClient(
        api_base_url="https://example.test/v1",
        model="text-embedding-test",
        transport=httpx.MockTransport(handler),
    )
    client.api_key = "test"
    vector = client.embed_text("hello world")
    assert vector == [0.1, 0.2, 0.3]
    client.close()


def test_embedding_client_fallback():
    client = EmbeddingClient(
        api_base_url="https://example.test/v1",
        model="text-embedding-test",
    )
    vector = client.embed_text("hello world")
    assert len(vector) == 256
    client.close()

