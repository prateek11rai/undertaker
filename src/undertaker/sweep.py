"""One sweep: list running workflows, snapshot each, and run the rules."""

from datetime import UTC, datetime

from undertaker.config import Thresholds
from undertaker.diagnose.rules import CAUSES, Diagnosis, diagnose
from undertaker.temporal.client import TemporalReader
from undertaker.temporal.evidence import Snapshot


async def sweep(reader: TemporalReader, th: Thresholds) -> list[Diagnosis]:
    """Diagnose every running workflow in the namespace.

    Args:
        reader: The Temporal reader.
        th: Rule thresholds.

    Returns:
        One diagnosis per running workflow, undead first.
    """
    reader.new_sweep()
    snaps: dict[str, Snapshot] = {}
    for wid, run in await reader.list_running():
        try:
            snaps[wid] = await reader.snapshot(wid, run)
        except Exception:
            continue
    now = datetime.now(UTC)
    results = diagnose_all(snaps, th, now)
    for wid, d in list(results.items()):
        if d.cause == "waiting-signal":
            snaps[wid].signal_names = await reader.signal_names(wid, d.run_id)
            results[wid] = diagnose(snaps[wid], th, now, lambda c: results.get(c))
    order = list(CAUSES)
    return sorted(results.values(), key=lambda d: (order.index(d.cause), d.workflow_id))


def diagnose_all(snaps: dict[str, Snapshot], th: Thresholds, now: datetime) -> dict[str, Diagnosis]:
    """Diagnose snapshots, children before parents (pure).

    Args:
        snaps: Snapshots by workflow id.
        th: Rule thresholds.
        now: The time to judge against.

    Returns:
        Diagnoses by workflow id.
    """
    results: dict[str, Diagnosis] = {}
    visiting: set[str] = set()

    def lookup(wid: str) -> Diagnosis | None:
        if wid in results:
            return results[wid]
        if wid not in snaps or wid in visiting:
            return None
        visiting.add(wid)
        results[wid] = diagnose(snaps[wid], th, now, lookup)
        return results[wid]

    for wid in snaps:
        lookup(wid)
    return results
