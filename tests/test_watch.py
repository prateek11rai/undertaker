from test_certificate import DIAG

from undertaker.watch import new_undead


def test_one_notification_per_workflow():
    seen: set[str] = set()
    first = new_undead(list(DIAG.values()), seen)
    assert {d.workflow_id for d in first} == {d.workflow_id for d in DIAG.values()}
    assert new_undead(list(DIAG.values()), seen) == []
