"""Sweep on a timer; one macOS notification per new undead workflow, never more."""

import asyncio
import json
import platform
import shutil
import subprocess
from pathlib import Path

from undertaker.config import Settings
from undertaker.diagnose.rules import Diagnosis

SCRIPT = [
    "-e",
    "on run argv",
    "-e",
    "display notification (item 1 of argv) with title (item 2 of argv)",
    "-e",
    "end run",
]


def notify(title: str, message: str) -> bool:
    """Post a macOS notification; text goes in as argv, never into the script."""
    if platform.system() != "Darwin" or not shutil.which("osascript"):
        return False
    subprocess.run(["osascript", *SCRIPT, message, title], check=False, capture_output=True)
    return True


def new_undead(results: list[Diagnosis], seen: set[str]) -> list[Diagnosis]:
    """Undead workflows not notified before (pure); adds them to seen."""
    out = []
    for d in results:
        if d.undead and d.workflow_id not in seen:
            seen.add(d.workflow_id)
            out.append(d)
    return out


def _load(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text()))
    except (OSError, ValueError):
        return set()


async def watch(s: Settings, once: bool = False) -> int:
    """Sweep every --every and notify once per new undead workflow."""
    from undertaker.commands import fact_line, reader_for
    from undertaker.sweep import sweep

    store = s.data_dir / "watch-notified.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    seen = _load(store)
    reader = await reader_for(s)
    print(
        f"Watching {s.address} {s.namespace} every {int(s.every.total_seconds())} s. "
        "Ctrl-C to stop."
    )
    while True:
        results = await sweep(reader, s.thresholds)
        for d in new_undead(results, seen):
            line = f"{d.workflow_id}: {d.label.lower()} ({fact_line(d)})"
            print(line)
            notify("undertaker", line)
        store.write_text(json.dumps(sorted(seen)))
        if once:
            return 0
        await asyncio.sleep(s.every.total_seconds())
