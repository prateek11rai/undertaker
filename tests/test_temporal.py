import asyncio
import os
import uuid
from datetime import timedelta

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from undertaker.config import Thresholds
from undertaker.demo.activities import ACTIVITIES
from undertaker.demo.workflows import (
    AwaitPaymentWorkflow,
    HolidayCakeWorkflow,
    PayOrderWorkflow,
    RecipeWorkflow,
)
from undertaker.sweep import sweep
from undertaker.temporal.client import TemporalReader

pytestmark = pytest.mark.temporal
TEMPORAL = os.environ.get("UNDERTAKER_TEMPORAL_BIN", "/opt/homebrew/bin/temporal")


async def test_sweep_finds_causes_and_actions_work():
    env = await WorkflowEnvironment.start_local(
        dev_server_existing_path=TEMPORAL, dev_server_extra_args=["--log-level", "error"]
    )
    try:
        client = env.client
        queue = f"it-{uuid.uuid4().hex[:6]}"
        worker = Worker(
            client,
            task_queue=queue,
            activities=ACTIVITIES,
            workflows=[PayOrderWorkflow, AwaitPaymentWorkflow, HolidayCakeWorkflow, RecipeWorkflow],
        )
        async with worker:
            for wf, arg, wid, q in [
                ("PayOrderWorkflow", 0, "it-retry", queue),
                ("AwaitPaymentWorkflow", "o", "it-signal", queue),
                ("HolidayCakeWorkflow", "c", "it-sleep", queue),
                ("RecipeWorkflow", "c", "it-broken", queue),
                ("NobodyWorkflow", "x", "it-orphan", "it-nobody"),
            ]:
                await client.start_workflow(wf, arg, id=wid, task_queue=q)
            await asyncio.sleep(6)
            reader = TemporalReader(client, client.namespace)
            th = Thresholds(quiet=timedelta(seconds=3), attempts=3)
            got = {d.workflow_id: d for d in await sweep(reader, th)}
            assert got["it-retry"].cause == "retry-loop"
            assert got["it-signal"].cause == "waiting-signal"
            assert got["it-signal"].details["signals"] == ["payment_received"]
            assert got["it-sleep"].cause == "long-sleep"
            assert got["it-broken"].cause == "broken-code"
            assert got["it-orphan"].cause == "orphaned"

            await reader.terminate("it-retry", "laid to rest by test")
            new_run = await reader.reset_last_task("it-broken", "resurrected by test")
            assert new_run and new_run != got["it-broken"].run_id
            running = {wid for wid, _ in await reader.list_running()}
            assert "it-retry" not in running
    finally:
        await env.shutdown()
