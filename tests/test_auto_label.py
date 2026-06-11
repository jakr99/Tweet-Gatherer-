import json

import pytest

from research_agent.auto_label import (
    AutoLabelResult,
    OpenAIClassifier,
    build_classification_payload,
    data_url_for_image,
    parse_label_response,
)
from research_agent.models import Candidate


def test_data_url_for_image_uses_base64_and_mime_type(tmp_path):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"fake-image")

    data_url = data_url_for_image(image)

    assert data_url.startswith("data:image/jpeg;base64,")


def test_build_classification_payload_includes_text_and_image(tmp_path):
    image = tmp_path / "sample.png"
    image.write_bytes(b"fake-image")
    candidate = Candidate(
        tweet_id="1",
        image_id="img",
        tweet_text="A flood of complaints hit the office.",
        image_path=str(image),
    )

    payload = build_classification_payload(candidate)

    content = payload["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert "A flood of complaints" in content[0]["text"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")


def test_parse_label_response_accepts_valid_json():
    response = json.dumps(
        {
            "text_label": "figurative",
            "image_label": "literal",
            "disaster_label": "not_real_disaster",
            "text_confidence": 0.9,
            "image_confidence": 0.8,
            "disaster_confidence": 0.7,
            "explanation": "The text is metaphorical.",
        }
    )

    result = parse_label_response(response)

    assert result == AutoLabelResult(
        text_label="figurative",
        image_label="literal",
        disaster_label="not_real_disaster",
        text_confidence=0.9,
        image_confidence=0.8,
        disaster_confidence=0.7,
        explanation="The text is metaphorical.",
    )


def test_parse_label_response_rejects_invalid_labels():
    response = json.dumps(
        {
            "text_label": "unclear",
            "image_label": "literal",
            "disaster_label": "not_real_disaster",
            "text_confidence": 0.9,
            "image_confidence": 0.8,
            "disaster_confidence": 0.7,
            "explanation": "bad",
        }
    )

    with pytest.raises(ValueError, match="Invalid text_label"):
        parse_label_response(response)


def test_openai_classifier_uses_fake_transport():
    calls = []

    def fake_transport(payload, api_key):
        calls.append((payload, api_key))
        return json.dumps(
            {
                "text_label": "literal",
                "image_label": "literal",
                "disaster_label": "real_disaster",
                "text_confidence": 0.91,
                "image_confidence": 0.92,
                "disaster_confidence": 0.93,
                "explanation": "Direct disaster report.",
            }
        )

    classifier = OpenAIClassifier(
        api_key="key",
        model="gpt-test",
        transport=fake_transport,
    )
    candidate = Candidate(
        tweet_id="1",
        image_id="img",
        tweet_text="Flooding downtown.",
        image_url="https://example.com/image.jpg",
    )

    result = classifier.classify(candidate)

    assert result.disaster_label == "real_disaster"
    assert calls[0][1] == "key"
    assert calls[0][0]["model"] == "gpt-test"
