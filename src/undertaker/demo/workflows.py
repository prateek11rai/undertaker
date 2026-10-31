"""Haunted-bakery workflows: one per cause of undeath, plus healthy ones."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

ORDERS = "bakery-orders"
OVENS = "bakery-ovens"
LEGACY = "bakery-legacy"
FOREVER = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=1.0,
    maximum_interval=timedelta(seconds=2),
    maximum_attempts=0,
)


@workflow.defn
class PayOrderWorkflow:
    """Charges a card for an order that costs nothing."""

    @workflow.run
    async def run(self, amount: int) -> str:
        """Charge the card."""
        return await workflow.execute_activity(
            "charge_card",
            amount,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=FOREVER,
        )


@workflow.defn
class BakeBatchWorkflow:
    """Bakes a batch in an oven that stops answering."""

    @workflow.run
    async def run(self, trays: int) -> str:
        """Bake the batch."""
        return await workflow.execute_activity(
            "bake_batch",
            trays,
            start_to_close_timeout=timedelta(hours=1),
            heartbeat_timeout=timedelta(seconds=5),
            retry_policy=FOREVER,
        )


@workflow.defn
class FireOvenWorkflow:
    """Sends work to an oven queue no worker polls."""

    @workflow.run
    async def run(self, oven: str) -> str:
        """Fire the oven."""
        return await workflow.execute_activity(
            "fire_oven", oven, task_queue=OVENS, start_to_close_timeout=timedelta(minutes=5)
        )


@workflow.defn
class RecipeWorkflow:
    """Reads an ingredient the recipe never had."""

    @workflow.run
    async def run(self, cake: str) -> str:
        """Follow the recipe."""
        recipe = {"flour": 500, "butter": 250}
        sugar = recipe["sugar"]
        return f"{cake} with {sugar} g sugar"


@workflow.defn(name="DecorateCakeWorkflow")
class DecorateCakeV1:
    """Version A: bake, rest, then frost."""

    @workflow.run
    async def run(self, cake: str) -> str:
        """Decorate the cake."""
        await workflow.execute_activity("bake", cake, start_to_close_timeout=timedelta(seconds=10))
        await workflow.sleep(timedelta(seconds=15))
        return await workflow.execute_activity(
            "frost", cake, start_to_close_timeout=timedelta(seconds=10)
        )


@workflow.defn(name="DecorateCakeWorkflow")
class DecorateCakeV2:
    """Version B: someone moved frosting first, without a patch."""

    @workflow.run
    async def run(self, cake: str) -> str:
        """Decorate the cake."""
        await workflow.execute_activity("frost", cake, start_to_close_timeout=timedelta(seconds=10))
        await workflow.sleep(timedelta(seconds=15))
        return await workflow.execute_activity(
            "bake", cake, start_to_close_timeout=timedelta(seconds=10)
        )


@workflow.defn
class AwaitPaymentWorkflow:
    """Waits for a payment that never arrives."""

    def __init__(self) -> None:
        self.paid = False

    @workflow.signal
    def payment_received(self) -> None:
        """Mark the order paid."""
        self.paid = True

    @workflow.run
    async def run(self, order: str) -> str:
        """Wait for payment, then pack."""
        await workflow.wait_condition(lambda: self.paid)
        return await workflow.execute_activity(
            "pack_box", order, start_to_close_timeout=timedelta(seconds=10)
        )


@workflow.defn
class HolidayCakeWorkflow:
    """Rests the dough for 365 days (meant 365 seconds)."""

    @workflow.run
    async def run(self, cake: str) -> str:
        """Rest, then bake."""
        await workflow.sleep(timedelta(days=365))
        return await workflow.execute_activity(
            "bake", cake, start_to_close_timeout=timedelta(seconds=10)
        )


@workflow.defn
class GiftBoxOrderWorkflow:
    """Waits on a child box workflow sent to the legacy queue."""

    @workflow.run
    async def run(self, order: str) -> str:
        """Pack the gift box through a child workflow."""
        return await workflow.execute_child_workflow(
            "BoxWorkflow", order, id=f"{order}-box", task_queue=LEGACY
        )


@workflow.defn
class InventoryWorkflow:
    """Counts the pantry shelves; slow, but alive."""

    @workflow.run
    async def run(self, shelves: int) -> int:
        """Count the shelves."""
        return await workflow.execute_activity(
            "count_shelves",
            shelves,
            start_to_close_timeout=timedelta(hours=12),
            heartbeat_timeout=timedelta(seconds=10),
        )


@workflow.defn
class ProofDoughWorkflow:
    """Proofs dough in short rounds, then finishes."""

    @workflow.run
    async def run(self, rounds: int) -> str:
        """Proof the dough."""
        for _ in range(rounds):
            await workflow.sleep(timedelta(seconds=90))
        return "proofed"


@workflow.defn
class SimpleOrderWorkflow:
    """A normal order: pack and done."""

    @workflow.run
    async def run(self, order: str) -> str:
        """Pack the order."""
        return await workflow.execute_activity(
            "pack_box", order, start_to_close_timeout=timedelta(seconds=10)
        )


WORKFLOWS = [
    PayOrderWorkflow,
    BakeBatchWorkflow,
    FireOvenWorkflow,
    RecipeWorkflow,
    DecorateCakeV2,
    AwaitPaymentWorkflow,
    HolidayCakeWorkflow,
    GiftBoxOrderWorkflow,
    InventoryWorkflow,
    ProofDoughWorkflow,
    SimpleOrderWorkflow,
]
