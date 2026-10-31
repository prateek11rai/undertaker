"""What each subcommand does."""

import argparse
import json
import os
import platform
import urllib.request
from datetime import UTC, datetime

from undertaker.config import DATA_DIR, TEMPORAL_BIN, Settings
from undertaker.diagnose.rules import Diagnosis, short_duration


async def run(args: argparse.Namespace) -> int:
    """Dispatch a parsed command."""
    from undertaker.cli import settings_from

    if args.cmd == "demo":
        return await demo(args.action)
    s = settings_from(args)
    if args.cmd == "doctor":
        return await doctor(s)
    if args.cmd == "sweep":
        return await sweep_cmd(s, args.json)
    if args.cmd == "inspect":
        from undertaker.explain.render import inspect_cmd

        return await inspect_cmd(s, args.workflow_id)
    if args.cmd == "serve":
        from undertaker.morgue.app import serve

        return await serve(s, args.port)
    if args.cmd == "eval":
        from undertaker.evals import eval_cmd

        return await eval_cmd(s)
    if args.cmd == "watch":
        from undertaker.watch import watch

        return await watch(s)
    return 2


async def reader_for(s: Settings):
    """Connect and return a TemporalReader."""
    from undertaker.temporal.client import TemporalReader, connect

    try:
        client = await connect(s.address, s.namespace)
    except Exception as e:
        raise SystemExit(f"Cannot reach Temporal at {s.address}: {e}") from None
    return TemporalReader(client, s.namespace)


def fact_line(d: Diagnosis, now: datetime | None = None) -> str:
    """'undead for 2 h 14 min · attempt 47', or the alive reason."""
    if not d.undead:
        return d.fact
    now = now or datetime.now(UTC)
    since = short_duration(now - d.undead_since) if d.undead_since else "?"
    return f"undead for {since} · {d.fact}"


async def sweep_cmd(s: Settings, as_json: bool) -> int:
    """Print the sweep as a table or JSON."""
    from undertaker.sweep import sweep

    reader = await reader_for(s)
    results = await sweep(reader, s.thresholds)
    if as_json:
        print(json.dumps([d.to_dict() for d in results], indent=2))
        return 0
    undead = sum(d.undead for d in results)
    print(f"{undead} undead · {len(results) - undead} alive · {s.address} {s.namespace}\n")
    rows = [("WORKFLOW ID", "TYPE", "CAUSE", "")]
    rows += [(d.workflow_id, d.workflow_type, d.cause, fact_line(d)) for d in results]
    w = [max(len(r[i]) for r in rows) for i in range(3)]
    for r in rows:
        print(f"{r[0]:<{w[0]}}  {r[1]:<{w[1]}}  {r[2]:<{w[2]}}  {r[3]}")
    return 0


async def demo(action: str) -> int:
    """Demo up | down | status."""
    from undertaker.demo.server import Demo

    d = Demo(DATA_DIR)
    if action == "up":
        out = await d.up()
        print(f"Demo up: Temporal {out['address']} (UI http://127.0.0.1:8233), worker running.")
        print(
            f"Seeded {len(out['expected'])} running workflows and "
            f"{len(out['completed'])} completed ones."
        )
        if "order-1047" not in out["expected"]:
            print("order-1047 (changed-code) could not be seeded this time.")
        print("Wait about 30 s for the thresholds, then: uv run undertaker sweep --demo")
    elif action == "down":
        stopped = d.down()
        print("Stopped: " + (", ".join(stopped) if stopped else "nothing was running"))
    else:
        st = d.status()
        print(f"temporal: {'running, pid ' + str(st['temporal']) if st['temporal'] else 'stopped'}")
        print(f"worker:   {'running, pid ' + str(st['worker']) if st['worker'] else 'stopped'}")
    return 0


def _get_json(url: str, timeout: float = 3) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
        return json.loads(r.read())


async def doctor(s: Settings) -> int:
    """Check Temporal, Ollama and the model, and print versions."""
    import temporalio.service

    ok = True
    print(f"python      {platform.python_version()}")
    try:
        from importlib.metadata import version

        print(f"temporalio  {version('temporalio')}")
    except Exception:
        pass
    found = "found" if os.path.exists(TEMPORAL_BIN) else "missing"
    print(f"temporal    {TEMPORAL_BIN} {found}")
    try:
        from undertaker.temporal.client import connect

        client = await connect(s.address, s.namespace)
        info = await client.workflow_service.get_system_info(
            temporalio.api.workflowservice.v1.GetSystemInfoRequest()
        )
        print(f"server      {s.address} reachable, version {info.server_version or '?'}")
    except Exception as e:
        ok = False
        print(f"server      {s.address} not reachable ({type(e).__name__})")
    try:
        v = _get_json(f"{s.ollama}/api/version")
        tags = _get_json(f"{s.ollama}/api/tags")
        names = [m.get("name") for m in tags.get("models", [])]
        print(f"ollama      {s.ollama} reachable, version {v.get('version')}")
        if s.model in names:
            print(f"model       {s.model} present")
        else:
            ok = False
            print(f"model       {s.model} missing (template certificates only)")
    except Exception as e:
        ok = False
        print(
            f"ollama      {s.ollama} not reachable ({type(e).__name__}); template certificates only"
        )
    return 0 if ok else 1
