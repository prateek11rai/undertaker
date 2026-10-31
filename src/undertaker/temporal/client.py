"""Temporal access: list, describe, history, pollers, metadata query, and the two actions.

This is the only module that touches protobufs; it hands plain Snapshots to the rules.
"""

import uuid
from datetime import UTC, datetime, timedelta

from temporalio.api.common.v1 import WorkflowExecution
from temporalio.api.enums.v1 import (
    EventType,
    PendingActivityState,
    PendingWorkflowTaskState,
    ResetReapplyType,
    TaskQueueType,
    TimeoutType,
    WorkflowTaskFailedCause,
)
from temporalio.api.failure.v1 import Failure as FailureProto
from temporalio.api.sdk.v1 import WorkflowMetadata
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import (
    DescribeTaskQueueRequest,
    DescribeWorkflowExecutionRequest,
    ResetWorkflowExecutionRequest,
)
from temporalio.client import Client

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


async def connect(address: str, namespace: str) -> Client:
    """Connect to a Temporal frontend."""
    return await Client.connect(address, namespace=namespace)


def _ts(ts) -> datetime | None:
    if ts is None or (ts.seconds == 0 and ts.nanos == 0):
        return None
    return ts.ToDatetime(tzinfo=UTC)


def _secs(d) -> float:
    return d.seconds + d.nanos / 1e9


def _event_name(n: int) -> str:
    name = EventType.Name(n).removeprefix("EVENT_TYPE_")
    return "".join(p.capitalize() for p in name.split("_"))


def failure_from_proto(f: FailureProto | None, cause: str = "") -> Failure | None:
    """Convert a Failure proto (the outermost one with a useful message) to a Failure."""
    if f is None or (not f.message and not f.stack_trace and not f.HasField("cause")):
        return None
    out = Failure(message=f.message, stack=f.stack_trace, cause=cause)
    if f.HasField("application_failure_info"):
        out.type = f.application_failure_info.type
    if f.HasField("timeout_failure_info"):
        out.timeout_type = TimeoutType.Name(f.timeout_failure_info.timeout_type)
        out.type = out.type or "TimeoutError"
    if not out.stack and f.HasField("cause"):
        inner = failure_from_proto(f.cause)
        if inner and inner.stack:
            out.stack = inner.stack
    return out


class History:
    """What the rules need from a workflow's history."""

    def __init__(self, events) -> None:
        self.last: Event | None = None
        self.scheduled: dict[str, tuple[Event, object]] = {}
        self.first_scheduled: dict[str, Event] = {}
        self.timers: dict[str, OpenTimer] = {}
        self.first_wft_failed: Event | None = None
        self.last_wft_failed: Event | None = None
        self.last_wft_failure: Failure | None = None
        self.events: list[Event] = []
        for e in events:
            self._add(e)

    def _add(self, e) -> None:
        name = _event_name(e.event_type)
        ev = Event(e.event_id, name, _ts(e.event_time))
        t = e.event_type
        if t == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED:
            a = e.activity_task_scheduled_event_attributes
            ev.detail = a.activity_type.name
            self.scheduled[a.activity_id] = (ev, a)
            self.first_scheduled.setdefault(a.activity_id, ev)
        elif t == EventType.EVENT_TYPE_TIMER_STARTED:
            a = e.timer_started_event_attributes
            secs = _secs(a.start_to_fire_timeout)
            fire = ev.time + timedelta(seconds=secs) if ev.time else None
            ev.detail = f"{secs:g} s"
            self.timers[a.timer_id] = OpenTimer(a.timer_id, e.event_id, ev.time, fire, secs)
        elif t == EventType.EVENT_TYPE_TIMER_FIRED:
            self.timers.pop(e.timer_fired_event_attributes.timer_id, None)
        elif t == EventType.EVENT_TYPE_TIMER_CANCELED:
            self.timers.pop(e.timer_canceled_event_attributes.timer_id, None)
        elif t == EventType.EVENT_TYPE_WORKFLOW_TASK_FAILED:
            a = e.workflow_task_failed_event_attributes
            cause = WorkflowTaskFailedCause.Name(a.cause)
            ev.detail = cause.removeprefix("WORKFLOW_TASK_FAILED_CAUSE_")
            self.first_wft_failed = self.first_wft_failed or ev
            self.last_wft_failed = ev
            self.last_wft_failure = failure_from_proto(a.failure, cause)
        elif t == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_SIGNALED:
            ev.detail = e.workflow_execution_signaled_event_attributes.signal_name
        elif t == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED:
            ev.detail = e.workflow_execution_started_event_attributes.workflow_type.name
        self.events.append(ev)
        self.last = ev


class TemporalReader:
    """Reads workflow state from one namespace, caching histories by last event id."""

    def __init__(self, client: Client, namespace: str) -> None:
        self.client = client
        self.namespace = namespace
        self._histories: dict[tuple[str, str, int], History] = {}
        self._pollers: dict[str, list[datetime]] = {}

    def new_sweep(self) -> None:
        """Forget poller info from the last sweep."""
        self._pollers = {}

    async def list_running(self) -> list[tuple[str, str]]:
        """Return (workflow id, run id) for every running workflow."""
        out = []
        async for w in self.client.list_workflows('ExecutionStatus="Running"'):
            out.append((w.id, w.run_id))
        return out

    async def history(self, wid: str, run: str, length: int) -> History:
        """Fetch and parse a history once per (id, run, length)."""
        key = (wid, run, length)
        if key not in self._histories:
            h = await self.client.get_workflow_handle(wid, run_id=run).fetch_history()
            self._histories[key] = History(h.events)
        return self._histories[key]

    async def pollers(self, queue: str, kind: str) -> list[datetime]:
        """Last access times of pollers on a task queue."""
        key = poller_key(queue, kind)
        if key not in self._pollers:
            tq_type = (
                TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW
                if kind == "workflow"
                else TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY
            )
            resp = await self.client.workflow_service.describe_task_queue(
                DescribeTaskQueueRequest(
                    namespace=self.namespace,
                    task_queue=TaskQueue(name=queue),
                    task_queue_type=tq_type,
                )
            )
            self._pollers[key] = [t for p in resp.pollers if (t := _ts(p.last_access_time))]
        return self._pollers[key]

    async def snapshot(self, wid: str, run: str) -> Snapshot:
        """Describe a workflow and join it with its history and pollers."""
        d = await self.client.workflow_service.describe_workflow_execution(
            DescribeWorkflowExecutionRequest(
                namespace=self.namespace, execution=WorkflowExecution(workflow_id=wid, run_id=run)
            )
        )
        info = d.workflow_execution_info
        run = info.execution.run_id or run
        h = await self.history(wid, run, info.history_length)
        snap = Snapshot(
            workflow_id=wid,
            run_id=run,
            workflow_type=info.type.name,
            task_queue=d.execution_config.task_queue.name or info.task_queue,
            start_time=_ts(info.start_time),
            history_length=info.history_length,
            last_event=h.last,
            open_timers=list(h.timers.values()),
            last_wft_failure=h.last_wft_failure,
            last_wft_failed_event=h.last_wft_failed,
            first_wft_failed_event=h.first_wft_failed,
        )
        if d.HasField("pending_workflow_task"):
            p = d.pending_workflow_task
            snap.pending_workflow_task = PendingWorkflowTask(
                state=PendingWorkflowTaskState.Name(p.state).removeprefix(
                    "PENDING_WORKFLOW_TASK_STATE_"
                ),
                scheduled_time=_ts(p.scheduled_time),
                attempt=p.attempt,
                original_scheduled_time=_ts(p.original_scheduled_time),
                started_time=_ts(p.started_time),
            )
        for p in d.pending_activities:
            sched = h.scheduled.get(p.activity_id)
            first = h.first_scheduled.get(p.activity_id)
            attrs = sched[1] if sched else None
            snap.pending_activities.append(
                PendingActivity(
                    activity_id=p.activity_id,
                    activity_type=p.activity_type.name,
                    state=PendingActivityState.Name(p.state).removeprefix(
                        "PENDING_ACTIVITY_STATE_"
                    ),
                    attempt=p.attempt,
                    maximum_attempts=p.maximum_attempts,
                    task_queue=attrs.task_queue.name if attrs else snap.task_queue,
                    scheduled_time=_ts(p.scheduled_time) or (sched[0].time if sched else None),
                    scheduled_event_id=sched[0].id if sched else None,
                    first_scheduled_time=first.time if first else None,
                    last_started_time=_ts(p.last_started_time),
                    last_heartbeat_time=_ts(p.last_heartbeat_time),
                    next_attempt_time=_ts(p.next_attempt_schedule_time),
                    heartbeat_timeout_s=_secs(attrs.heartbeat_timeout) if attrs else None,
                    last_failure=failure_from_proto(p.last_failure)
                    if p.HasField("last_failure")
                    else None,
                )
            )
        for c in d.pending_children:
            snap.pending_children.append(
                PendingChild(c.workflow_id, c.run_id, c.workflow_type_name)
            )
        snap.pollers[poller_key(snap.task_queue, "workflow")] = await self.pollers(
            snap.task_queue, "workflow"
        )
        for a in snap.pending_activities:
            snap.pollers[poller_key(a.task_queue, "activity")] = await self.pollers(
                a.task_queue, "activity"
            )
        return snap

    async def signal_names(self, wid: str, run: str) -> list[str] | None:
        """Ask the worker for the workflow's signal and update names (built-in metadata query)."""
        try:
            md = await self.client.get_workflow_handle(wid, run_id=run).query(
                "__temporal_workflow_metadata",
                result_type=WorkflowMetadata,
                rpc_timeout=timedelta(seconds=3),
            )
        except Exception:
            return None
        names = [s.name for s in md.definition.signal_definitions]
        names += [u.name for u in md.definition.update_definitions]
        return [n for n in names if n and not n.startswith("__")]

    async def terminate(self, wid: str, reason: str) -> None:
        """Terminate (lay to rest) a workflow's current run."""
        await self.client.get_workflow_handle(wid).terminate(reason=reason)

    async def reset_last_task(self, wid: str, reason: str) -> str:
        """Reset (resurrect) a workflow to its last workflow task; return the new run id."""
        handle = self.client.get_workflow_handle(wid)
        desc = await handle.describe()
        h = await handle.fetch_history()
        finish = [
            e.event_id
            for e in h.events
            if e.event_type
            in (
                EventType.EVENT_TYPE_WORKFLOW_TASK_COMPLETED,
                EventType.EVENT_TYPE_WORKFLOW_TASK_FAILED,
                EventType.EVENT_TYPE_WORKFLOW_TASK_TIMED_OUT,
            )
        ]
        if not finish:
            finish = [
                e.event_id
                for e in h.events
                if e.event_type == EventType.EVENT_TYPE_WORKFLOW_TASK_STARTED
            ]
        if not finish:
            raise RuntimeError("no workflow task to reset to")
        resp = await self.client.workflow_service.reset_workflow_execution(
            ResetWorkflowExecutionRequest(
                namespace=self.namespace,
                workflow_execution=WorkflowExecution(workflow_id=wid, run_id=desc.run_id),
                reason=reason,
                workflow_task_finish_event_id=finish[-1],
                request_id=str(uuid.uuid4()),
                reset_reapply_type=ResetReapplyType.RESET_REAPPLY_TYPE_SIGNAL,
            )
        )
        return resp.run_id
