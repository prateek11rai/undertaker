"""Ollama over HTTP with the standard library; JSON-schema output."""

import json
import urllib.request

from undertaker.explain.certificate import SCHEMA


class ModelError(Exception):
    """Ollama could not be reached or did not answer with JSON."""


def chat(base: str, model: str, messages: list[dict], timeout: float = 180) -> dict:
    """One chat call returning the parsed JSON object.

    Args:
        base: Ollama base URL (local).
        model: Model name, e.g. gemma4:e4b.
        messages: Chat messages.
        timeout: Seconds to wait.

    Returns:
        The model's JSON answer.

    Raises:
        ModelError: On any transport or parse failure.
    """
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": SCHEMA,
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            data = json.loads(r.read())
        out = json.loads(data["message"]["content"])
    except Exception as e:
        raise ModelError(f"{type(e).__name__}: {e}") from None
    if not isinstance(out, dict):
        raise ModelError("answer is not a JSON object")
    return out
