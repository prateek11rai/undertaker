"""Seeds the haunted bakery: one workflow per cause, two alive, three completed."""

import asyncio
from datetime import timedelta

from temporalio.api.enums.v1 import EventType
from temporalio.client import Client
from temporalio.worker import Worker

from undertaker.demo.activities import bake, frost
from undertaker.demo.workflows import LEGACY, ORDERS, DecorateCakeV1


async def seed_changed_code(client: Client) -> bool:
    """Start order-1047 on version A until it sleeps, then stop version A.

    The demo worker (version B) picks it up when the timer fires, and fails on replay.

    Returns:
        True if order-1047 reached its timer under version A.
    """
    worker = Worker(
        client,
        task_queue=ORDERS,
        workflows=[DecorateCakeV1],
        activities=[bake, frost],
        max_cached_workflows=0,
    )
    async with worker:
        handle = await client.start_workflow(
            "DecorateCakeWorkflow", "pumpkin cake", id="order-1047", task_queue=ORDERS
        )
        for _ in range(60):
            history = await handle.fetch_history()
            if any(e.event_type == EventType.EVENT_TYPE_TIMER_STARTED for e in history.events):
                return True
            await asyncio.sleep(0.5)
    return False


async def seed_rest(client: Client) -> None:
    """Start every other demo workflow on the running demo worker."""
    starts = [
        ("PayOrderWorkflow", 0, "order-1042", ORDERS),
        ("BakeBatchWorkflow", 12, "order-1043", ORDERS),
        ("FireOvenWorkflow", "oven-3", "order-1044", ORDERS),
        ("LegacyOrderWorkflow", "order-1045", "order-1045", LEGACY),
        ("RecipeWorkflow", "lemon tart", "order-1046", ORDERS),
        ("AwaitPaymentWorkflow", "order-1048", "order-1048", ORDERS),
        ("HolidayCakeWorkflow", "stollen", "order-1049", ORDERS),
        ("GiftBoxOrderWorkflow", "order-1050", "order-1050", ORDERS),
        ("InventoryWorkflow", 21600, "inventory-nightly", ORDERS),
        ("ProofDoughWorkflow", 20, "proof-dough", ORDERS),
    ]
    for wf, arg, wid, queue in starts:
        await client.start_workflow(wf, arg, id=wid, task_queue=queue, execution_timeout=None)
    done = []
    for n in (1001, 1002, 1003):
        done.append(
            await client.start_workflow(
                "SimpleOrderWorkflow",
                f"order-{n}",
                id=f"order-{n}",
                task_queue=ORDERS,
                run_timeout=timedelta(minutes=5),
            )
        )
    await asyncio.wait_for(asyncio.gather(*(h.result() for h in done)), timeout=60)
