"""The certificate as text, for ``undertaker inspect``."""

import textwrap
from datetime import UTC, datetime

from undertaker.config import Settings
from undertaker.diagnose.remedies import remedy
from undertaker.diagnose.rules import Diagnosis, short_duration
from undertaker.explain.writer import Written


def when(t: datetime | str | None) -> str:
    """'31 Oct 2026, 22:05' in local time."""
    if not t:
        return "unknown"
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    return t.astimezone().strftime("%d %b %Y, %H:%M:%S")


def written_by(w: Written) -> str:
    """Who wrote the words, said plainly."""
    c = w.cert
    if c.source == "model":
        retry = " on the second try" if c.tries == 2 else ""
        return f"written by {c.model}{retry}, every fact checked"
    if c.model:
        return f"template certificate ({c.model} was rejected or unavailable)"
    return "template certificate (model off)"


def text(d: Diagnosis, w: Written | None, s: Settings) -> str:
    """The whole certificate as plain text."""
    out = []
    wrap = textwrap.TextWrapper(width=88, subsequent_indent=" " * 20)

    def field(label: str, value: str) -> None:
        out.append(wrap.fill(f"{label:<19} {value}"))

    out.append("CERTIFICATE OF UNDEATH" if d.undead else "STILL ALIVE")
    out.append(f"{d.workflow_id} · run {d.run_id[:8]}… · {d.workflow_type} · {d.task_queue}")
    if w:
        out.append(written_by(w))
    out.append("-" * 88)
    field("Born", when(d.born))
    if d.last_event:
        le = d.last_event
        field("Last sign of life", f"event {le['id']}, {le['type']}, {when(le['time'])}")
    field("Cause", f"{d.label} ({d.cause})")
    if d.undead and d.undead_since:
        field("Undead for", short_duration(datetime.now(UTC) - d.undead_since))
    if w:
        field("Headline", w.cert.headline)
        field("Diagnosis", w.cert.diagnosis)
        field("Next step", w.cert.next_step)
    else:
        field("Why alive", d.fact)
    out.append("-" * 88)
    out.append("Evidence")
    for e in d.evidence:
        t = f"  ({when(e.time)})" if e.time else ""
        out.append(f"  {e.key:<18} {e.text}{t}")
    if w and w.excerpts:
        for x in w.excerpts:
            out.append("-" * 88)
            out.append(f"Source {x.file}:{x.line}")
            out.append(x.text)
    if d.undead:
        r = remedy(d, s.address, s.namespace)
        out.append("-" * 88)
        field("Remedy", r.sentence)
        for c in r.commands:
            out.append(f"  {c.label}:\n    {c.cmd}")
    if w and w.cert.epitaph:
        out.append("-" * 88)
        out.append(f'"{w.cert.epitaph}"')
    return "\n".join(out)


async def inspect_cmd(s: Settings, workflow_id: str) -> int:
    """Sweep, then print one workflow's certificate."""
    from undertaker.commands import reader_for
    from undertaker.explain.cache import CertCache
    from undertaker.explain.writer import write
    from undertaker.sweep import sweep

    reader = await reader_for(s)
    results = {d.workflow_id: d for d in await sweep(reader, s.thresholds)}
    d = results.get(workflow_id)
    if not d:
        print(f"{workflow_id} is not a running workflow in {s.namespace}.")
        return 1
    w = write(d, s, CertCache(s.data_dir / "certificates.sqlite")) if d.undead else None
    print(text(d, w, s))
    return 0
