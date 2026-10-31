from dataclasses import replace

from test_certificate import DIAG

from undertaker.evals import score


def test_score_found_missed_false_alarm_and_finished_alive():
    results = [
        replace(DIAG["retry-loop"], workflow_id="a"),
        replace(DIAG["long-sleep"], workflow_id="b"),
    ]
    expected = {"a": "retry-loop", "b": "waiting-signal", "c": "alive", "x": "orphaned"}
    sc = score(results, expected)
    assert sc.found == ["a"]
    assert ("b", "waiting-signal", "long-sleep") in sc.missed
    assert ("x", "orphaned", "not running") in sc.missed
    assert sc.alive_ok == ["c"]
    assert sc.false_alarms == []


def test_unexpected_undead_is_false_alarm():
    d = DIAG["heartbeat"]
    sc = score([d], {})
    assert sc.false_alarms == [(d.workflow_id, "heartbeat")]
