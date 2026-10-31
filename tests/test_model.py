from datetime import timedelta
from pathlib import Path

import pytest
from helpers import NOW, activity, failure, snap

import undertaker.demo.activities as demo_activities
from undertaker.config import Settings, Thresholds
from undertaker.diagnose.rules import diagnose
from undertaker.explain.certificate import check
from undertaker.explain.writer import write

pytestmark = pytest.mark.model


def test_gemma_writes_a_checked_certificate(tmp_path):
    src = Path(demo_activities.__file__)
    stack = (
        f'Traceback (most recent call last):\n  File "{src}", line 12, in charge_card\n'
        '    raise ValueError("amount must be positive")\n'
    )
    s = snap(
        workflow_id="order-1042",
        workflow_type="PayOrderWorkflow",
        task_queue="bakery-orders",
        pending_activities=[activity(attempt=47, last_failure=failure(stack=stack))],
    )
    d = diagnose(s, Thresholds(quiet=timedelta(seconds=20), attempts=3), NOW)
    assert d.cause == "retry-loop"
    w = write(d, Settings(data_dir=tmp_path, source=src.parent))
    c = w.cert
    print(c.source, c.tries, c.seconds, c.rejected)
    assert c.tries >= 1 and c.model == "gemma4:e4b"
    assert w.excerpts and w.excerpts[0].file == "activities.py"
    raw = {k: getattr(c, k) for k in ("headline", "diagnosis", "evidence", "next_step", "epitaph")}
    assert check(raw, d, w.excerpts) == []
