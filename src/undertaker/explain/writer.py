"""Writes one certificate: model, checks, one retry with reasons, else the template."""

import json
import time
from dataclasses import dataclass

from undertaker.config import Settings
from undertaker.diagnose.rules import Diagnosis
from undertaker.explain.cache import CertCache
from undertaker.explain.certificate import SYSTEM, Certificate, check, prompt, template
from undertaker.explain.model import ModelError, chat
from undertaker.explain.source import Excerpt, excerpts


@dataclass
class Written:
    """A certificate with the source excerpts it was written from."""

    cert: Certificate
    excerpts: list[Excerpt]


def cache_key(d: Diagnosis, s: Settings) -> str:
    """Cache key for a diagnosis under these settings."""
    src = "src" if s.source else "nosrc"
    return f"{d.workflow_id}|{d.run_id}|{d.history_length}|{d.pending_attempt}|{s.model}|{src}"


def write(d: Diagnosis, s: Settings, cache: CertCache | None = None) -> Written:
    """The certificate for an undead diagnosis.

    Args:
        d: The diagnosis (must be undead).
        s: Settings (model, Ollama, source folder, no_model).
        cache: Optional cache.

    Returns:
        The certificate, from the model if it passed the checks, else the template.
    """
    xs = excerpts(d.frames, s.source)
    if s.no_model:
        return Written(template(d), xs)
    key = cache_key(d, s)
    if cache and (hit := cache.get(key)):
        return Written(hit, xs)
    started = time.monotonic()
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt(d, xs)}]
    rejected: list[str] = []
    cert = None
    done = 0
    for tries in (1, 2):
        done = tries
        try:
            raw = chat(s.ollama, s.model, messages)
        except ModelError as e:
            rejected.append(f"model error: {e}")
            break
        reasons = check(raw, d, xs)
        if not reasons:
            cert = Certificate(
                raw["headline"].strip(),
                raw["diagnosis"].strip(),
                list(raw["evidence"]),
                raw["next_step"].strip(),
                raw["epitaph"].strip().strip('"'),
                source="model",
                model=s.model,
                tries=tries,
            )
            break
        rejected += reasons
        messages += [
            {"role": "assistant", "content": json.dumps(raw)},
            {
                "role": "user",
                "content": "Rejected because: "
                + "; ".join(reasons)
                + ". Write it again and fix exactly these problems.",
            },
        ]
    if cert is None:
        cert = template(d)
        cert.model, cert.tries = s.model, done
    cert.rejected = rejected
    cert.seconds = round(time.monotonic() - started, 1)
    cert.attempt, cert.last_event_id = d.pending_attempt, d.history_length
    if cache and not any(r.startswith("model error") for r in rejected):
        cache.put(key, cert)
    return Written(cert, xs)
