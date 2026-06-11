from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_agent.http import ssl_context
from research_agent.models import DISASTER_LABELS, IMAGE_LABELS, TEXT_LABELS, Candidate


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.5"


@dataclass(frozen=True)
class AutoLabelResult:
    text_label: str
    image_label: str
    disaster_label: str
    text_confidence: float
    image_confidence: float
    disaster_confidence: float
    explanation: str


Transport = Callable[[dict[str, Any], str], str]


class OpenAIClassifier:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport or openai_responses_transport

    def classify(self, candidate: Candidate) -> AutoLabelResult:
        payload = build_classification_payload(candidate)
        payload["model"] = self.model
        return parse_label_response(self.transport(payload, self.api_key))


def data_url_for_image(path: str | Path) -> str:
    path = Path(path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def build_classification_payload(candidate: Candidate) -> dict[str, Any]:
    image_url = _image_input_url(candidate)
    if not image_url:
        raise ValueError("Candidate has no image_path or image_url for classification.")
    prompt = _classification_prompt(candidate)
    return {
        "model": DEFAULT_OPENAI_MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
    }


def parse_label_response(response_text: str) -> AutoLabelResult:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model response was not valid JSON: {exc}") from exc

    text_label = _required_label(payload, "text_label", TEXT_LABELS - {"unknown"})
    image_label = _required_label(payload, "image_label", IMAGE_LABELS - {"unknown"})
    disaster_label = _required_label(
        payload,
        "disaster_label",
        DISASTER_LABELS - {"unknown"},
    )
    return AutoLabelResult(
        text_label=text_label,
        image_label=image_label,
        disaster_label=disaster_label,
        text_confidence=_confidence(payload, "text_confidence"),
        image_confidence=_confidence(payload, "image_confidence"),
        disaster_confidence=_confidence(payload, "disaster_confidence"),
        explanation=str(payload.get("explanation", ""))[:1000],
    )


def openai_responses_transport(payload: dict[str, Any], api_key: str) -> str:
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=60,
            context=ssl_context(),
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API request failed with HTTP {exc.code}: {detail}") from exc
    return _extract_output_text(body)


def _extract_output_text(body: dict[str, Any]) -> str:
    if "output_text" in body:
        return str(body["output_text"])
    chunks: list[str] = []
    for output in body.get("output", []):
        for content in output.get("content", []):
            if "text" in content:
                chunks.append(str(content["text"]))
    if not chunks:
        raise ValueError("OpenAI response did not include output text.")
    return "\n".join(chunks)


def _image_input_url(candidate: Candidate) -> str:
    if candidate.image_path and Path(candidate.image_path).exists():
        return data_url_for_image(candidate.image_path)
    return candidate.image_url


def _classification_prompt(candidate: Candidate) -> str:
    return f"""Classify this tweet-image pair for disaster communication research.

Return strict JSON only with these keys:
text_label, image_label, disaster_label, text_confidence, image_confidence, disaster_confidence, explanation.

Allowed labels:
- text_label: literal or figurative
- image_label: literal or figurative
- disaster_label: real_disaster or not_real_disaster

Definitions:
- literal text: direct description without metaphor, idiom, analogy, personification, or symbolic phrasing.
- figurative text: metaphor, idiom, analogy, personification, hyperbole, symbolic language, or other non-literal phrasing.
- literal image: directly depicts the event, object, place, or situation referenced by the tweet.
- figurative image: supports meaning symbolically, metaphorically, emotionally, humorously, or by analogy.
- real_disaster: refers to an actual disaster, emergency, hazard, crisis, or response context.
- not_real_disaster: disaster language or imagery outside an actual disaster context.

Tweet text:
{candidate.tweet_text}
"""


def _required_label(
    payload: dict[str, Any],
    key: str,
    allowed: set[str],
) -> str:
    value = payload.get(key)
    if value not in allowed:
        raise ValueError(f"Invalid {key}: {value}")
    return str(value)


def _confidence(payload: dict[str, Any], key: str) -> float:
    value = float(payload.get(key, 0))
    if not 0 <= value <= 1:
        raise ValueError(f"Invalid {key}: {value}")
    return value
