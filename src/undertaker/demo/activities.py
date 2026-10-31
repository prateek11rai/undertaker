"""Haunted-bakery activities. Some are broken on purpose."""

import asyncio

from temporalio import activity


@activity.defn
async def charge_card(amount: int) -> str:
    """Charge the customer for an order."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    return f"charged {amount}"


@activity.defn
async def bake_batch(trays: int) -> str:
    """Bake a batch of trays; heartbeats once, then the oven goes quiet."""
    activity.heartbeat("oven warming")
    await asyncio.sleep(60)
    return f"baked {trays} trays"


@activity.defn
async def bake(cake: str) -> str:
    """Bake a cake."""
    return f"baked {cake}"


@activity.defn
async def frost(cake: str) -> str:
    """Frost a cake."""
    return f"frosted {cake}"


@activity.defn
async def pack_box(order: str) -> str:
    """Pack an order into a box."""
    return f"packed {order}"


@activity.defn
async def count_shelves(shelves: int) -> int:
    """Count every shelf in the pantry, slowly, reporting progress."""
    for shelf in range(shelves):
        activity.heartbeat(shelf)
        await asyncio.sleep(2)
    return shelves


ACTIVITIES = [charge_card, bake_batch, bake, frost, pack_box, count_shelves]
