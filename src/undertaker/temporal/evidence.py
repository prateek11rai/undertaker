"""Plain data classes for one workflow's state, and helpers that turn it into evidence."""

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import PurePath


@dataclass
class Event:
    """One history event, summarised."""

    id: int
    type: str
    time: datetime | None
    detail: str = ""


@dataclass
class Frame:
    """One stack frame from a failure's stack trace."""

    path: str
    line: int
    func: str

    @property
    def short(self) -> str:
        """File name, line and function, e.g. ``activities.py:42 in charge_card``."""
        return f"{PurePath(self.path).name}:{self.line} in {self.func}"


@dataclass
class Failure:
    """A failure as Temporal reports it."""

    type: str = ""
    message: str = ""
    stack: str = ""
    timeout_type: str = ""
    cause: str = ""

    @property
    def frames(self) -> list[Frame]:
        """User stack frames, innermost first."""
        return parse_frames(self.stack)

    @property
    def text(self) -> str:
        """``Type: message``, truncated."""
        msg = self.message.strip().splitlines()[0] if self.message.strip() else ""
        out = f"{self.type}: {msg}" if self.type else msg
        return out[:240]


@dataclass
class PendingActivity:
    """A pending activity from describe, joined with its scheduled event."""

    activity_id: str
    activity_type: str
    state: str
    attempt: int
    maximum_attempts: int
    task_queue: str
    scheduled_time: datetime | None
    scheduled_event_id: int | None = None
    first_scheduled_time: datetime | None = None
    last_started_time: datetime | None = None
    last_heartbeat_time: datetime | None = None
    next_attempt_time: datetime | None = None
    heartbeat_timeout_s: float | None = None
    last_failure: Failure | None = None


@dataclass
class PendingWorkflowTask:
    """The pending workflow task from describe."""

    state: str
    scheduled_time: datetime | None
    attempt: int
    original_scheduled_time: datetime | None = None
    started_time: datetime | None = None


@dataclass
class PendingChild:
    """A pending child workflow."""

    workflow_id: str
    run_id: str
    workflow_type: str


@dataclass
class OpenTimer:
    """A timer started and not yet fired or cancelled."""

    timer_id: str
    event_id: int
    started: datetime | None
    fire_time: datetime | None
    seconds: float


@dataclass
class Snapshot:
    """All the Temporal data the rules look at for one running workflow."""

    workflow_id: str
    run_id: str
    workflow_type: str
    task_queue: str
    start_time: datetime | None
    history_length: int
    last_event: Event | None
    pending_activities: list[PendingActivity] = field(default_factory=list)
    pending_workflow_task: PendingWorkflowTask | None = None
    pending_children: list[PendingChild] = field(default_factory=list)
    open_timers: list[OpenTimer] = field(default_factory=list)
    last_wft_failure: Failure | None = None
    last_wft_failed_event: Event | None = None
    first_wft_failed_event: Event | None = None
    pollers: dict[str, list[datetime]] = field(default_factory=dict)
    signal_names: list[str] | None = None


@dataclass
class EvidenceItem:
    """One small keyed fact a certificate may cite."""

    key: str
    text: str
    kind: str = "fact"
    time: datetime | None = None

    def to_dict(self) -> dict:
        """JSON-friendly form."""
        d = asdict(self)
        d["time"] = self.time.isoformat() if self.time else None
        return d


def poller_key(queue: str, kind: str) -> str:
    """Key into ``Snapshot.pollers`` for a task queue and kind ('workflow' or 'activity')."""
    return f"{kind}:{queue}"


_FRAME_RE = re.compile(r'File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<func>[\w<>.]+)')
_SKIP = ("site-packages", "/temporalio/", "<frozen", "/asyncio/", "/lib/python3")


def parse_frames(stack: str) -> list[Frame]:
    """Parse Python traceback frames, innermost first, skipping library frames.

    Args:
        stack: The stack trace text.

    Returns:
        Frames from user code, innermost first.
    """
    frames = [
        Frame(m["path"], int(m["line"]), m["func"])
        for m in _FRAME_RE.finditer(stack or "")
        if not any(s in m["path"] for s in _SKIP)
    ]
    return list(reversed(frames))


def event_item(ev: Event) -> EvidenceItem:
    """Evidence for a history event, keyed ``e<id>``."""
    text = f"{ev.type} {ev.detail}".strip()
    return EvidenceItem(key=f"e{ev.id}", text=text, kind="event", time=ev.time)


def frame_items(failure: Failure | None, limit: int = 3) -> list[EvidenceItem]:
    """Evidence for the top user frames of a failure, keyed ``frame1``.."""
    if not failure:
        return []
    return [
        EvidenceItem(key=f"frame{i}", text=f.short, kind="frame")
        for i, f in enumerate(failure.frames[:limit], start=1)
    ]
