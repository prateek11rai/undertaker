"""The demo worker: runs the bakery's workflows (version B) and activities."""

import asyncio
import signal
import sys

from temporalio.client import Client
from temporalio.worker import Worker

from undertaker.demo.activities import ACTIVITIES
from undertaker.demo.workflows import ORDERS, WORKFLOWS


async def run(address: str) -> None:
    """Poll the orders queue until SIGTERM or SIGINT."""
    client = await Client.connect(address)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    worker = Worker(client, task_queue=ORDERS, workflows=WORKFLOWS, activities=ACTIVITIES)
    async with worker:
        await stop.wait()


def main() -> None:
    """Entry point for ``python -m undertaker.demo.worker``."""
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:7233"))


if __name__ == "__main__":
    main()
