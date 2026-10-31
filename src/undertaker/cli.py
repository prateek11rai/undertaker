"""The ``undertaker`` command line."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from undertaker.config import DEMO_THRESHOLDS, Settings, Thresholds, parse_duration


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(f"UNDERTAKER_{name.upper().replace('-', '_')}", default)


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--address", default=_env("address", "127.0.0.1:7233"))
    p.add_argument("--namespace", default=_env("namespace", "default"))
    p.add_argument("--model", default=_env("model", "gemma4:e4b"))
    p.add_argument("--ollama", default=_env("ollama", "http://127.0.0.1:11434"))
    p.add_argument("--source", default=_env("source"), help="folder with the workflow code")
    p.add_argument("--no-model", action="store_true", help="template certificates only")
    p.add_argument("--demo", action="store_true", help=f"demo thresholds {DEMO_THRESHOLDS}")
    p.add_argument("--quiet", default=_env("quiet"), help="default 10m")
    p.add_argument("--attempts", default=_env("attempts"), help="default 5")
    p.add_argument("--poller-window", default=_env("poller_window"), help="default 2m")
    p.add_argument("--long-sleep", default=_env("long_sleep"), help="default 7d")


def settings_from(args: argparse.Namespace) -> Settings:
    """Build Settings from parsed arguments."""
    demo = getattr(args, "demo", False) or _env("demo") == "1"
    th = Thresholds()
    quiet = args.quiet or (DEMO_THRESHOLDS["quiet"] if demo else None)
    attempts = args.attempts or (DEMO_THRESHOLDS["attempts"] if demo else None)
    if quiet:
        th.quiet = parse_duration(quiet)
    if attempts:
        th.attempts = int(attempts)
    if args.poller_window:
        th.poller_window = parse_duration(args.poller_window)
    if args.long_sleep:
        th.long_sleep = parse_duration(args.long_sleep)
    s = Settings(
        address=args.address,
        namespace=args.namespace,
        model=args.model,
        ollama=args.ollama.rstrip("/"),
        thresholds=th,
        no_model=getattr(args, "no_model", False),
        allow_actions=getattr(args, "allow_actions", False),
    )
    if args.source:
        s.source = Path(args.source).resolve()
        if not s.source.is_dir():
            raise SystemExit(f"--source is not a folder: {args.source}")
    if getattr(args, "every", None):
        s.every = parse_duration(args.every)
    return s


def build_parser() -> argparse.ArgumentParser:
    """The argument parser for every subcommand."""
    p = argparse.ArgumentParser(
        prog="undertaker",
        description=("Finds the Temporal workflows that will never finish, and tells you why."),
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sweep", help="table of every running workflow and its cause")
    _common(s)
    s.add_argument("--json", action="store_true")
    i = sub.add_parser("inspect", help="the certificate for one workflow")
    _common(i)
    i.add_argument("workflow_id")
    v = sub.add_parser("serve", help="the morgue on 127.0.0.1:8666")
    _common(v)
    v.add_argument("--port", type=int, default=int(_env("port", "8666")))
    v.add_argument("--every", default=_env("every", "30s"))
    v.add_argument("--allow-actions", action="store_true", help="enable lay to rest / resurrect")
    w = sub.add_parser("watch", help="notify for each new undead (macOS)")
    _common(w)
    w.add_argument("--every", default=_env("every", "60s"))
    w.add_argument("--once", action="store_true", help="one sweep, then exit")
    e = sub.add_parser("eval", help="score the sweep against the demo manifest")
    _common(e)
    d = sub.add_parser("demo", help="the haunted bakery: up | down | status")
    d.add_argument("action", choices=["up", "down", "status"])
    doc = sub.add_parser("doctor", help="check Temporal, Ollama and the model")
    _common(doc)
    return p


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args = build_parser().parse_args(argv)
    from undertaker import commands

    return asyncio.run(commands.run(args)) or 0


if __name__ == "__main__":
    sys.exit(main())
