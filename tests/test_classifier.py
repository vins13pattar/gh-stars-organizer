from datetime import UTC, datetime

import httpx

from gh_stars_organizer.classifier import RepositoryClassifier
from gh_stars_organizer.models import Repository


def test_classifier_uses_model_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"category": "backend-api-frameworks"}',
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    classifier = RepositoryClassifier(
        api_base_url="https://example.test/v1",
        model="gpt-test",
        categories=["backend-api-frameworks", "other"],
        transport=transport,
    )
    repo = Repository(
        id="1",
        name="fastapi",
        owner="fastapi",
        full_name="fastapi/fastapi",
        description="Modern web API framework",
        topics=["api"],
        primary_language="Python",
        stargazer_count=1,
        url="https://github.com/fastapi/fastapi",
        updated_at=datetime.now(UTC),
    )
    assert classifier.classify(repo) == "backend-api-frameworks"
    classifier.close()

