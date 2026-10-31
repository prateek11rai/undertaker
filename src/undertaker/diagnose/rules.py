"""The nine causes of undeath, plus alive. Pure functions over a Snapshot."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from undertaker.config import Thresholds
from undertaker.temporal.evidence import (
    EvidenceItem,
    Frame,
    Snapshot,
    event_item,
    frame_items,
    poller_key,
)

CAUSES: dict[str, tuple[str, str]] = {
    "orphaned": (
        "No one is listening",
        "A workflow task is scheduled and was never started, and no worker polls its task queue.",
    ),
    "lost-activity": (
        "Sent to a worker that never came",
        "An activity is scheduled and was never started, and no worker polls its task queue.",
    ),
    "broken-code": (
        "Its own code keeps killing it",
        "Its workflow task fails on every attempt with an error from the workflow code.",
    ),
    "changed-code": (
        "Its code changed while it slept",
        "Its workflow task fails on every attempt with a non-determinism error on replay.",
    ),
    "heartbeat": (
        "Stopped breathing",
        "An activity keeps timing out on its heartbeat and is retried without end.",
    ),
    "retry-loop": (
        "Dies and rises, forever",
        "An activity fails the same way on every attempt and its retry policy has no limit.",
    ),
    "undead-child": (
        "Waiting on an undead child",
        "It waits on a child workflow that is itself undead.",
    ),
    "long-sleep": (
        "Asleep for a very long time",
        "It waits on a timer that fires far in the future.",
    ),
    "waiting-signal": (
        "Waiting for a visitor who never comes",
        "Nothing is scheduled at all; it can only wake on a signal or update.",
    ),
    "alive": ("Alive", "It is making progress or has a timer due soon."),
}
UNDEAD = [k for k in CAUSES if k != "alive"]


@dataclass
class Diagnosis:
    """The result of the rules for one workflow."""

    cause: str
    workflow_id: str
    run_id: str
    workflow_type: str
    task_queue: str
    born: datetime | None
    last_event: dict | None
    undead_since: datetime | None
    fact: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    pending_attempt: int = 0
    history_length: int = 0

    @property
    def undead(self) -> bool:
        """True for every cause except alive."""
        return self.cause != "alive"

    @property
    def label(self) -> str:
        """The cause as shown to people."""
        return CAUSES[self.cause][0]

    @property
    def rule(self) -> str:
        """The rule text for the cause."""
        return CAUSES[self.cause][1]

    def evidence_keys(self) -> set[str]:
        """Keys a certificate may cite."""
        return {e.key for e in self.evidence}

    def to_dict(self) -> dict:
        """JSON-friendly form."""
        return {
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "workflow_type": self.workflow_type,
            "task_queue": self.task_queue,
            "cause": self.cause,
            "label": self.label,
            "fact": self.fact,
            "born": _iso(self.born),
            "undead_since": _iso(self.undead_since),
            "last_event": self.last_event,
            "evidence": [e.to_dict() for e in self.evidence],
            "details": self.details,
        }


def _iso(t: datetime | None) -> str | None:
    return t.isoformat() if t else None


def _ago(now: datetime, t: datetime | None) -> timedelta:
    return now - t if t else timedelta(0)


def short_duration(d: timedelta) -> str:
    """Human duration like '2 h 14 min', '41 min', '12 s', '365 d'."""
    s = int(max(d.total_seconds(), 0))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    if s < 86400:
        return f"{s // 3600} h {s % 3600 // 60} min"
    return f"{s // 86400} d"


def _pollers(snap: Snapshot, queue: str, kind: str, now: datetime, window: timedelta) -> int:
    return sum(1 for t in snap.pollers.get(poller_key(queue, kind), []) if now - t <= window)


def _poller_item(n: int, queue: str, kind: str) -> EvidenceItem:
    return EvidenceItem("pollers", f"{n} pollers on {queue} ({kind})", kind="pollers")


def _base(snap: Snapshot, cause: str, since: datetime | None, fact: str, ev: list) -> Diagnosis:
    last = None
    if snap.last_event:
        le = snap.last_event
        last = {"id": le.id, "type": le.type, "time": _iso(le.time)}
    wft = snap.pending_workflow_task
    act = max((a.attempt for a in snap.pending_activities), default=0)
    return Diagnosis(
        cause=cause,
        workflow_id=snap.workflow_id,
        run_id=snap.run_id,
        workflow_type=snap.workflow_type,
        task_queue=snap.task_queue,
        born=snap.start_time,
        last_event=last,
        undead_since=since,
        fact=fact,
        evidence=ev,
        pending_attempt=max(wft.attempt if wft else 0, act),
        history_length=snap.history_length,
    )


def rule_orphaned(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 1: workflow task scheduled, never started, and no poller on its queue."""
    wft = snap.pending_workflow_task
    if not wft or wft.state != "SCHEDULED" or wft.started_time:
        return None
    since = wft.original_scheduled_time or wft.scheduled_time
    if _ago(now, since) <= th.quiet:
        return None
    n = _pollers(snap, snap.task_queue, "workflow", now, th.poller_window)
    if n:
        return None
    ev = [
        EvidenceItem("queue", f"workflow task queue {snap.task_queue}"),
        _poller_item(0, snap.task_queue, "workflow"),
        EvidenceItem("task", "workflow task scheduled, never started", time=since),
    ]
    d = _base(snap, "orphaned", since, f"0 pollers on {snap.task_queue}", ev)
    d.details["queue"] = snap.task_queue
    return d


def rule_lost_activity(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 2: activity scheduled, never started, and no poller on its queue."""
    for a in snap.pending_activities:
        if a.state != "SCHEDULED" or _ago(now, a.scheduled_time) <= th.quiet:
            continue
        if _pollers(snap, a.task_queue, "activity", now, th.poller_window):
            continue
        ev = [
            EvidenceItem("activity", f"activity {a.activity_type}"),
            EvidenceItem("queue", f"activity task queue {a.task_queue}"),
            _poller_item(0, a.task_queue, "activity"),
            EvidenceItem("attempt", str(a.attempt)),
        ]
        if a.scheduled_event_id:
            ev.insert(
                0,
                EvidenceItem(
                    f"e{a.scheduled_event_id}",
                    f"ActivityTaskScheduled {a.activity_type}",
                    kind="event",
                    time=a.first_scheduled_time,
                ),
            )
        d = _base(snap, "lost-activity", a.scheduled_time, f"0 pollers on {a.task_queue}", ev)
        d.details.update(queue=a.task_queue, activity=a.activity_type)
        return d
    return None


def is_nondeterminism(snap: Snapshot) -> bool:
    """True if the last workflow task failure is a non-determinism error."""
    f = snap.last_wft_failure
    if not f:
        return False
    blob = f"{f.cause} {f.type} {f.message}".lower()
    return "tmprl1100" in blob or "nondetermin" in blob or "non_deterministic" in blob


def _rule_wft(snap: Snapshot, th: Thresholds, now: datetime, nd: bool) -> Diagnosis | None:
    wft = snap.pending_workflow_task
    f = snap.last_wft_failure
    if not wft or wft.attempt < 2 or not f or is_nondeterminism(snap) != nd:
        return None
    cause = "changed-code" if nd else "broken-code"
    first = snap.first_wft_failed_event or snap.last_wft_failed_event
    ev = []
    if snap.last_wft_failed_event:
        ev.append(event_item(snap.last_wft_failed_event))
    ev += [
        EvidenceItem("task_attempt", str(wft.attempt)),
        EvidenceItem("failure", f.text, kind="failure"),
    ]
    ev += frame_items(f)
    d = _base(snap, cause, first.time if first else None, f"task attempt {wft.attempt}", ev)
    d.frames = f.frames[:3]
    return d


def rule_broken_code(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 3: workflow task keeps failing with a plain error."""
    return _rule_wft(snap, th, now, nd=False)


def rule_changed_code(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 4: workflow task keeps failing with a non-determinism error."""
    return _rule_wft(snap, th, now, nd=True)


def _activity_ev(a) -> list[EvidenceItem]:
    ev = []
    if a.scheduled_event_id:
        ev.append(
            EvidenceItem(
                f"e{a.scheduled_event_id}",
                f"ActivityTaskScheduled {a.activity_type}",
                kind="event",
                time=a.first_scheduled_time,
            )
        )
    ev += [
        EvidenceItem("activity", f"activity {a.activity_type}"),
        EvidenceItem("attempt", str(a.attempt)),
        EvidenceItem(
            "max_attempts", "no maximum" if not a.maximum_attempts else str(a.maximum_attempts)
        ),
    ]
    if a.last_failure:
        ev.append(EvidenceItem("failure", a.last_failure.text, kind="failure"))
    return ev


def rule_heartbeat(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 5: activity attempt over the threshold, last failure a heartbeat timeout."""
    for a in snap.pending_activities:
        f = a.last_failure
        if a.attempt < th.attempts or not f or "HEARTBEAT" not in f.timeout_type.upper():
            continue
        ev = _activity_ev(a)
        if a.heartbeat_timeout_s:
            ev.append(
                EvidenceItem("heartbeat_timeout", f"heartbeat timeout {a.heartbeat_timeout_s:g} s")
            )
        if a.last_heartbeat_time:
            ev.append(EvidenceItem("last_heartbeat", "last heartbeat", time=a.last_heartbeat_time))
        d = _base(
            snap,
            "heartbeat",
            a.first_scheduled_time or a.scheduled_time,
            f"attempt {a.attempt} · heartbeat timeout",
            ev,
        )
        d.details["activity"] = a.activity_type
        return d
    return None


def rule_retry_loop(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 6: activity attempt over the threshold, a real failure, no retry limit in sight."""
    for a in snap.pending_activities:
        f = a.last_failure
        if a.attempt < th.attempts or not f or f.timeout_type:
            continue
        if a.maximum_attempts and a.maximum_attempts - a.attempt < 50:
            continue
        ev = _activity_ev(a) + frame_items(f)
        d = _base(
            snap,
            "retry-loop",
            a.first_scheduled_time or a.scheduled_time,
            f"attempt {a.attempt}",
            ev,
        )
        d.frames = f.frames[:3]
        d.details["activity"] = a.activity_type
        return d
    return None


def rule_long_sleep(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 8: an open timer longer than --long-sleep."""
    for t in snap.open_timers:
        if t.seconds <= th.long_sleep.total_seconds():
            continue
        fire = t.fire_time.strftime("%d %b %Y") if t.fire_time else "unknown"
        ev = [
            EvidenceItem(
                f"e{t.event_id}",
                f"TimerStarted {short_duration(timedelta(seconds=t.seconds))}",
                kind="event",
                time=t.started,
            ),
            EvidenceItem("timer", f"timer fires {fire}", time=t.fire_time),
        ]
        d = _base(snap, "long-sleep", t.started, f"timer fires {fire}", ev)
        d.details["fire_time"] = _iso(t.fire_time)
        return d
    return None


def rule_waiting_signal(snap: Snapshot, th: Thresholds, now: datetime) -> Diagnosis | None:
    """Rule 9: nothing pending, last event older than --quiet."""
    if (
        snap.pending_activities
        or snap.open_timers
        or snap.pending_children
        or snap.pending_workflow_task
        or not snap.last_event
    ):
        return None
    le = snap.last_event
    if _ago(now, le.time) <= th.quiet:
        return None
    ev = [event_item(le), EvidenceItem("pending", "no activity, timer, child or workflow task")]
    if snap.signal_names:
        ev.append(EvidenceItem("signals", "handles signals " + ", ".join(snap.signal_names)))
    d = _base(snap, "waiting-signal", le.time, "nothing scheduled", ev)
    d.details["signals"] = snap.signal_names or []
    return d


BEFORE_CHILD: list[Callable] = [
    rule_orphaned,
    rule_lost_activity,
    rule_broken_code,
    rule_changed_code,
    rule_heartbeat,
    rule_retry_loop,
]
AFTER_CHILD: list[Callable] = [rule_long_sleep, rule_waiting_signal]


def alive(snap: Snapshot, now: datetime, children: dict[str, "Diagnosis"]) -> Diagnosis:
    """The alive result, with the reason it looks alive."""
    reason = f"started {short_duration(_ago(now, snap.start_time))} ago"
    for a in snap.pending_activities:
        if a.last_heartbeat_time:
            reason = f"heartbeat {short_duration(_ago(now, a.last_heartbeat_time))} ago"
        elif a.state == "STARTED" and a.last_started_time:
            reason = (
                f"activity attempt {a.attempt}, started "
                f"{short_duration(_ago(now, a.last_started_time))} ago"
            )
        else:
            reason = f"activity {a.activity_type} attempt {a.attempt}"
        break
    else:
        if snap.open_timers:
            t = min(snap.open_timers, key=lambda t: t.fire_time or now)
            left = t.fire_time - now if t.fire_time else timedelta()
            reason = f"timer fires in {short_duration(left)}"
        elif snap.pending_children:
            reason = f"waiting on child {snap.pending_children[0].workflow_id}"
        elif snap.pending_workflow_task:
            reason = f"workflow task attempt {snap.pending_workflow_task.attempt}"
        elif snap.last_event:
            reason = f"last event {short_duration(_ago(now, snap.last_event.time))} ago"
    ev = [EvidenceItem("reason", reason)]
    if snap.last_event:
        ev.insert(0, event_item(snap.last_event))
    return _base(snap, "alive", None, reason, ev)


def diagnose(
    snap: Snapshot,
    th: Thresholds,
    now: datetime | None = None,
    lookup: Callable[[str], "Diagnosis | None"] | None = None,
) -> Diagnosis:
    """Run the rules in spec order; the first match is the cause.

    Args:
        snap: The workflow's state.
        th: Thresholds.
        now: The time to judge against (UTC).
        lookup: Returns the diagnosis of a child workflow by id, if known.

    Returns:
        The diagnosis.
    """
    now = now or datetime.now(UTC)
    for rule in BEFORE_CHILD:
        if d := rule(snap, th, now):
            return d
    children: dict[str, Diagnosis] = {}
    for c in snap.pending_children:
        cd = lookup(c.workflow_id) if lookup else None
        if cd:
            children[c.workflow_id] = cd
        if cd and cd.undead:
            ev = [
                EvidenceItem("child", f"child {c.workflow_id} ({c.workflow_type})"),
                EvidenceItem("child_cause", f"child cause {cd.cause}: {cd.label}"),
            ]
            d = _base(snap, "undead-child", cd.undead_since, f"child {c.workflow_id}", ev)
            d.details.update(child=c.workflow_id, child_cause=cd.cause)
            return d
    for rule in AFTER_CHILD:
        if d := rule(snap, th, now):
            return d
    return alive(snap, now, children)
