"""Score a sweep against the demo manifest, and the model against its checks."""

import asyncio
import json
import statistics
from dataclasses import dataclass, field

from undertaker.config import Settings
from undertaker.demo.manifest import MANIFEST
from undertaker.diagnose.rules import Diagnosis
from undertaker.explain.writer import write


@dataclass
class Score:
    """Rule and model results for one eval run."""

    found: list[str] = field(default_factory=list)
    missed: list[tuple[str, str, str]] = field(default_factory=list)
    false_alarms: list[tuple[str, str]] = field(default_factory=list)
    alive_ok: list[str] = field(default_factory=list)


def score(results: list[Diagnosis], expected: dict[str, str]) -> Score:
    """Compare diagnoses with the expected cause per workflow id (pure).

    Args:
        results: Sweep results.
        expected: Workflow id to expected cause.

    Returns:
        Found, missed and false alarms. An expected-alive workflow that already
        finished counts as fine.
    """
    got = {d.workflow_id: d.cause for d in results}
    s = Score()
    for wid, want in expected.items():
        have = got.get(wid)
        if want == "alive":
            if have in (None, "alive"):
                s.alive_ok.append(wid)
            else:
                s.false_alarms.append((wid, have))
        elif have == want:
            s.found.append(wid)
        else:
            s.missed.append((wid, want, have or "not running"))
    for wid, have in got.items():
        if wid not in expected and have != "alive":
            s.false_alarms.append((wid, have))
    return s


async def eval_cmd(s: Settings) -> int:
    """Run the demo eval and print the numbers."""
    from undertaker.commands import reader_for
    from undertaker.sweep import sweep

    manifest_file = s.data_dir / "manifest.json"
    expected = (
        json.loads(manifest_file.read_text())["expected"]
        if manifest_file.exists()
        else dict(MANIFEST)
    )
    reader = await reader_for(s)
    results = await sweep(reader, s.thresholds)
    sc = score(results, expected)
    undead_expected = sum(1 for c in expected.values() if c != "alive")
    print(
        f"Rules: found {len(sc.found)}/{undead_expected} · missed {len(sc.missed)} · "
        f"false alarms {len(sc.false_alarms)} · alive ok {len(sc.alive_ok)}"
    )
    for wid, want, have in sc.missed:
        print(f"  missed {wid}: expected {want}, got {have}")
    for wid, have in sc.false_alarms:
        print(f"  false alarm {wid}: {have}")
    out = {"found": sc.found, "missed": sc.missed, "false_alarms": sc.false_alarms}
    if not s.no_model:
        counts = {"accepted": 0, "retried": 0, "fallback": 0}
        secs, reasons = [], []
        for d in results:
            if not d.undead:
                continue
            w = await asyncio.to_thread(write, d, s, None)
            c = w.cert
            kind = "fallback" if c.source != "model" else "retried" if c.tries == 2 else "accepted"
            counts[kind] += 1
            secs.append(c.seconds)
            reasons += [f"{d.workflow_id}: {r}" for r in c.rejected]
            print(f"  {d.workflow_id:<16} {d.cause:<15} {kind:<9} {c.seconds:5.1f} s")
        n = sum(counts.values())
        mean = statistics.mean(secs) if secs else 0
        print(
            f"Model {s.model}: accepted {counts['accepted']}/{n} · retried then accepted "
            f"{counts['retried']} · fallback {counts['fallback']} · {mean:.1f} s per certificate"
        )
        for r in reasons:
            print(f"  rejected {r}")
        out |= {"model": s.model, **counts, "seconds_mean": round(mean, 1), "rejected": reasons}
    (s.data_dir / "eval.json").write_text(json.dumps(out, indent=2))
    return 0 if not sc.missed and not sc.false_alarms else 1
