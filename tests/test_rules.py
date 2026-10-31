from datetime import timedelta

import pytest
from helpers import NOW, activity, ago, child, failure, snap, timer, wft

from undertaker.config import Thresholds
from undertaker.diagnose.rules import CAUSES, UNDEAD, diagnose, short_duration
from undertaker.sweep import diagnose_all
from undertaker.temporal.evidence import Event, Failure, parse_frames, poller_key

TH = Thresholds(quiet=timedelta(seconds=20), attempts=3)


def cause(s, lookup=None):
    return diagnose(s, TH, NOW, lookup).cause


def test_nine_causes_plus_alive():
    assert len(UNDEAD) == 9
    assert list(CAUSES)[-1] == "alive"


def test_orphaned():
    s = snap(
        task_queue="legacy",
        pending_workflow_task=wft(scheduled_time=ago(60)),
        pollers={},
        last_event=Event(2, "WorkflowTaskScheduled", ago(60)),
    )
    d = diagnose(s, TH, NOW)
    assert d.cause == "orphaned"
    assert "0 pollers on legacy" in d.fact
    assert "pollers" in d.evidence_keys()


def test_orphaned_near_miss_has_poller():
    s = snap(pending_workflow_task=wft(scheduled_time=ago(60)))
    assert cause(s) != "orphaned"


def test_orphaned_near_miss_too_recent():
    s = snap(pending_workflow_task=wft(scheduled_time=ago(5)), pollers={})
    assert cause(s) == "alive"


def test_orphaned_near_miss_old_poller_outside_window():
    s = snap(
        pending_workflow_task=wft(scheduled_time=ago(60)),
        pollers={poller_key("orders", "workflow"): [ago(600)]},
    )
    assert cause(s) == "orphaned"


def test_lost_activity():
    s = snap(
        pending_activities=[
            activity(task_queue="ovens", scheduled_time=ago(60), activity_type="fire_oven")
        ]
    )
    d = diagnose(s, TH, NOW)
    assert d.cause == "lost-activity"
    assert d.details["queue"] == "ovens"


def test_lost_activity_near_miss_queue_polled():
    s = snap(pending_activities=[activity(scheduled_time=ago(60))])
    assert cause(s) == "alive"


def test_broken_code():
    s = snap(
        pending_workflow_task=wft(attempt=4),
        last_wft_failure=failure("'sugar'", "KeyError"),
        last_wft_failed_event=Event(4, "WorkflowTaskFailed", ago(100)),
    )
    d = diagnose(s, TH, NOW)
    assert d.cause == "broken-code"
    assert {"e4", "task_attempt", "failure", "frame1"} <= d.evidence_keys()


def test_broken_code_near_miss_first_attempt():
    s = snap(pending_workflow_task=wft(attempt=1), last_wft_failure=failure())
    assert cause(s) == "alive"


@pytest.mark.parametrize(
    "msg,cause_name",
    [
        ("[TMPRL1100] Nondeterminism error: Activity type does not match", ""),
        ("whatever", "WORKFLOW_TASK_FAILED_CAUSE_NON_DETERMINISTIC_ERROR"),
    ],
)
def test_changed_code(msg, cause_name):
    s = snap(
        pending_workflow_task=wft(attempt=3),
        last_wft_failure=Failure(message=msg, cause=cause_name),
    )
    assert cause(s) == "changed-code"


def test_heartbeat():
    f = Failure(
        type="TimeoutError",
        message="activity Heartbeat timeout",
        timeout_type="TIMEOUT_TYPE_HEARTBEAT",
    )
    s = snap(pending_activities=[activity(attempt=5, last_failure=f, heartbeat_timeout_s=5)])
    d = diagnose(s, TH, NOW)
    assert d.cause == "heartbeat"
    assert "heartbeat_timeout" in d.evidence_keys()


def test_heartbeat_near_miss_few_attempts():
    f = Failure(timeout_type="TIMEOUT_TYPE_HEARTBEAT")
    s = snap(pending_activities=[activity(attempt=2, last_failure=f)])
    assert cause(s) == "alive"


def test_retry_loop():
    s = snap(pending_activities=[activity(attempt=47, last_failure=failure())])
    d = diagnose(s, TH, NOW)
    assert d.cause == "retry-loop"
    assert d.fact == "attempt 47"
    frame = next(e for e in d.evidence if e.key == "frame1")
    assert frame.text == "activities.py:42 in charge_card"


def test_retry_loop_near_miss_limit_close():
    s = snap(pending_activities=[activity(attempt=8, maximum_attempts=10, last_failure=failure())])
    assert cause(s) == "alive"


def test_retry_loop_near_miss_start_to_close_timeout():
    f = Failure(timeout_type="TIMEOUT_TYPE_START_TO_CLOSE")
    s = snap(pending_activities=[activity(attempt=8, last_failure=f)])
    assert cause(s) == "alive"


def test_undead_child_and_children_first():
    parent = snap(workflow_id="order-1", pending_children=[child("order-1-box")])
    box = snap(
        workflow_id="order-1-box",
        task_queue="legacy",
        pollers={},
        pending_workflow_task=wft(scheduled_time=ago(60)),
    )
    res = diagnose_all({"order-1": parent, "order-1-box": box}, TH, NOW)
    assert res["order-1-box"].cause == "orphaned"
    assert res["order-1"].cause == "undead-child"
    assert res["order-1"].details["child"] == "order-1-box"


def test_undead_child_near_miss_child_alive():
    parent = snap(workflow_id="order-1", pending_children=[child("order-1-box")])
    box = snap(workflow_id="order-1-box", open_timers=[timer(30)])
    res = diagnose_all({"order-1": parent, "order-1-box": box}, TH, NOW)
    assert res["order-1"].cause == "alive"
    assert "order-1-box" in res["order-1"].fact


def test_long_sleep():
    s = snap(open_timers=[timer(365 * 86400)])
    d = diagnose(s, TH, NOW)
    assert d.cause == "long-sleep"
    assert d.fact.startswith("timer fires ")


def test_long_sleep_near_miss_short_timer():
    d = diagnose(snap(open_timers=[timer(90, started_ago=50)]), TH, NOW)
    assert d.cause == "alive"
    assert d.fact == "timer fires in 40 s"


def test_waiting_signal_lists_signals():
    s = snap(signal_names=["payment_received"])
    d = diagnose(s, TH, NOW)
    assert d.cause == "waiting-signal"
    assert "payment_received" in next(e.text for e in d.evidence if e.key == "signals")


def test_waiting_signal_near_miss_recent_event():
    s = snap(last_event=Event(11, "WorkflowTaskCompleted", ago(3)))
    assert cause(s) == "alive"


def test_alive_heartbeat_reason():
    s = snap(pending_activities=[activity(state="STARTED", last_heartbeat_time=ago(3))])
    assert diagnose(s, TH, NOW).fact == "heartbeat 3 s ago"


def test_rule_order_orphaned_before_waiting():
    s = snap(pending_workflow_task=wft(scheduled_time=ago(60)), pollers={})
    assert cause(s) == "orphaned"


def test_parse_frames_skips_library():
    from helpers import STACK

    frames = parse_frames(STACK)
    assert [f.short for f in frames] == ["activities.py:42 in charge_card"]


def test_short_duration():
    assert short_duration(timedelta(seconds=12)) == "12 s"
    assert short_duration(timedelta(minutes=41)) == "41 min"
    assert short_duration(timedelta(hours=2, minutes=14)) == "2 h 14 min"
