"""Remedies per cause: one plain sentence and the exact commands. The model never writes these."""

import shlex
from dataclasses import dataclass, field

from undertaker.diagnose.rules import Diagnosis


@dataclass
class Command:
    """One copyable command."""

    label: str
    cmd: str


@dataclass
class Remedy:
    """What to do about one undead workflow."""

    sentence: str
    commands: list[Command] = field(default_factory=list)
    child: str | None = None


def _flags(address: str, namespace: str) -> str:
    return f"--address {shlex.quote(address)} --namespace {shlex.quote(namespace)}"


def remedy(d: Diagnosis, address: str, namespace: str) -> Remedy:
    """The code-made remedy for a diagnosis.

    Args:
        d: The diagnosis.
        address: Temporal frontend address, filled into commands.
        namespace: Namespace, filled into commands.

    Returns:
        The remedy sentence and commands.
    """
    f = _flags(address, namespace)
    wid = shlex.quote(d.workflow_id)
    reason = shlex.quote(f"undertaker: {d.cause}")
    terminate = Command(
        "Lay to rest", f"temporal workflow terminate --workflow-id {wid} --reason {reason} {f}"
    )
    reset = Command(
        "Resurrect",
        f"temporal workflow reset --workflow-id {wid} "
        f"--type LastWorkflowTask --reason {reason} {f}",
    )
    q = shlex.quote(d.details.get("queue", d.task_queue))
    c = d.cause
    if c == "orphaned":
        return Remedy(
            f"Start a worker that polls `{d.details.get('queue')}`, or lay it to rest.",
            [
                Command("Check pollers", f"temporal task-queue describe --task-queue {q} {f}"),
                terminate,
            ],
        )
    if c == "lost-activity":
        return Remedy(
            f"Start a worker that polls `{d.details.get('queue')}` for activity "
            f"`{d.details.get('activity')}`, or lay it to rest.",
            [
                Command(
                    "Check pollers",
                    f"temporal task-queue describe --task-queue {q} --task-queue-type activity {f}",
                ),
                terminate,
            ],
        )
    if c == "broken-code":
        return Remedy(
            "Fix the workflow code and deploy, or reset past the bad task.", [reset, terminate]
        )
    if c == "changed-code":
        return Remedy(
            "Put the old path back behind `workflow.patched` and deploy, then reset "
            "past the bad task.",
            [reset, terminate],
        )
    if c in ("heartbeat", "retry-loop"):
        what = (
            "Fix the activity so it heartbeats in time" if c == "heartbeat" else "Fix the activity"
        )
        return Remedy(
            f"{what}, or mark the error non-retryable. Until then it will not stop.", [terminate]
        )
    if c == "waiting-signal":
        cmds = [
            Command(
                "Send signal",
                f"temporal workflow signal --workflow-id {wid} "
                f"--name {shlex.quote(s)} --input '{{}}' {f}",
            )
            for s in d.details.get("signals", [])
        ]
        known = (
            "It handles " + ", ".join(f"`{s}`" for s in d.details["signals"]) + ". "
            if d.details.get("signals")
            else ""
        )
        return Remedy(
            f"{known}Send the signal it waits for, or lay it to rest. Undertaker "
            "can't know whether the signal is still coming.",
            cmds + [terminate],
        )
    if c == "long-sleep":
        fire = d.fact.removeprefix("timer fires ")
        return Remedy(
            f"The timer fires on {fire}. If the duration is a mistake, fix it and "
            "reset, or lay it to rest.",
            [reset, terminate],
        )
    if c == "undead-child":
        child = d.details.get("child", "")
        return Remedy(
            f"Fix the child `{child}` first; this workflow follows it.",
            [
                Command(
                    "Describe child",
                    f"temporal workflow describe --workflow-id {shlex.quote(child)} {f}",
                ),
                terminate,
            ],
            child=child,
        )
    return Remedy("Nothing to do; it is making progress.")
