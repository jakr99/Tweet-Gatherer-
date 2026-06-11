from research_agent.x_api import XApiClient, candidates_from_search_response, ssl_context


def test_candidates_from_search_response_maps_image_media():
    payload = {
        "data": [
            {
                "id": "10",
                "text": "Wildfire smoke blankets the valley.",
                "author_id": "42",
                "created_at": "2026-06-11T12:00:00Z",
                "attachments": {"media_keys": ["3_abc", "3_def"]},
            }
        ],
        "includes": {
            "media": [
                {
                    "media_key": "3_abc",
                    "type": "photo",
                    "url": "https://pbs.twimg.com/media/abc.jpg",
                    "width": 1200,
                    "height": 800,
                },
                {
                    "media_key": "3_def",
                    "type": "video",
                    "preview_image_url": "https://pbs.twimg.com/media/def.jpg",
                },
            ]
        },
    }

    candidates = candidates_from_search_response(
        payload,
        source_query_name="wildfire_real",
        source_query="wildfire has:images -is:retweet",
        seed_labels={"disaster_label": "real_disaster"},
    )

    assert len(candidates) == 1
    assert candidates[0].tweet_id == "10"
    assert candidates[0].image_id == "3_abc"
    assert candidates[0].image_url == "https://pbs.twimg.com/media/abc.jpg"
    assert candidates[0].tweet_text == "Wildfire smoke blankets the valley."
    assert candidates[0].author_id == "42"
    assert candidates[0].source == "x_api"
    assert candidates[0].source_query == "wildfire_real"
    assert candidates[0].disaster_label == "real_disaster"


def test_recent_search_request_params_include_media_expansions():
    client = XApiClient("token")

    params = client.recent_search_params("flood has:images", max_results=25)

    assert params["query"] == "flood has:images"
    assert params["max_results"] == "25"
    assert "attachments.media_keys" in params["expansions"]
    assert "url" in params["media.fields"]


def test_ssl_context_uses_certifi_bundle():
    context = ssl_context()

    assert context.get_ca_certs()
