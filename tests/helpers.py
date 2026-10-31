from datetime import UTC, datetime, timedelta

from undertaker.temporal.evidence import (
    Event,
    Failure,
    OpenTimer,
    PendingActivity,
    PendingChild,
    PendingWorkflowTask,
    Snapshot,
    poller_key,
)

NOW = datetime(2026, 10, 31, 22, 0, tzinfo=UTC)
STACK = """Traceback (most recent call last):
  File "/x/site-packages/temporalio/worker/_activity.py", line 300, in _run
    return await impl()
  File "/src/bakery/activities.py", line 42, in charge_card
    raise ValueError("amount must be positive")
"""


def ago(s: float) -> datetime:
    return NOW - timedelta(seconds=s)


def snap(**kw) -> Snapshot:
    base = dict(
        workflow_id="order-1",
        run_id="run-1",
        workflow_type="OrderWorkflow",
        task_queue="orders",
        start_time=ago(3600),
        history_length=11,
        last_event=Event(11, "WorkflowTaskCompleted", ago(3000)),
        pollers={
            poller_key("orders", "workflow"): [ago(5)],
            poller_key("orders", "activity"): [ago(5)],
        },
    )
    base.update(kw)
    return Snapshot(**base)


def activity(**kw) -> PendingActivity:
    base = dict(
        activity_id="1",
        activity_type="charge_card",
        state="SCHEDULED",
        attempt=1,
        maximum_attempts=0,
        task_queue="orders",
        scheduled_time=ago(5),
        scheduled_event_id=5,
        first_scheduled_time=ago(3000),
    )
    base.update(kw)
    return PendingActivity(**base)


def failure(msg="amount must be positive", typ="ValueError", **kw) -> Failure:
    return Failure(type=typ, message=msg, stack=kw.pop("stack", STACK), **kw)


def wft(**kw) -> PendingWorkflowTask:
    base = dict(state="SCHEDULED", scheduled_time=ago(5), attempt=1)
    base.update(kw)
    return PendingWorkflowTask(**base)


def timer(seconds: float, started_ago: float = 10) -> OpenTimer:
    start = ago(started_ago)
    return OpenTimer("1", 5, start, start + timedelta(seconds=seconds), seconds)


def child(wid="order-1-box") -> PendingChild:
    return PendingChild(wid, "r", "BoxWorkflow")
