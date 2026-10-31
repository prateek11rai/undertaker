"""Lifecycle of the demo: the Homebrew dev server and the demo worker as background processes."""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from temporalio.client import Client

from undertaker.config import TEMPORAL_BIN
from undertaker.demo.manifest import COMPLETED, MANIFEST
from undertaker.demo.seed import seed_changed_code, seed_rest

ADDRESS = "127.0.0.1:7233"


class Demo:
    """Starts, seeds and stops the haunted bakery under a data folder."""

    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir
        self.server_pid = data_dir / "temporal.pid"
        self.worker_pid = data_dir / "worker.pid"

    def _alive(self, pidfile: Path) -> int | None:
        """The pid in a pid file if that process is alive."""
        try:
            pid = int(pidfile.read_text())
            os.kill(pid, 0)
            return pid
        except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
            return None

    def _spawn(self, args: list[str], log: str, pidfile: Path) -> int:
        with open(self.dir / log, "ab") as out:
            p = subprocess.Popen(
                args,
                stdout=out,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        pidfile.write_text(str(p.pid))
        return p.pid

    def _stop(self, pidfile: Path) -> bool:
        pid = self._alive(pidfile)
        if pid:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(50):
                if not self._alive(pidfile):
                    break
                time.sleep(0.2)
            else:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for _ in range(25):
                if not self._alive(pidfile):
                    break
                time.sleep(0.2)
        pidfile.unlink(missing_ok=True)
        return bool(pid)

    def start_server(self) -> None:
        """Start a fresh dev server on 127.0.0.1 with its db and log under the data folder."""
        if not Path(TEMPORAL_BIN).exists():
            raise SystemExit(f"Temporal CLI not found at {TEMPORAL_BIN}")
        self.dir.mkdir(parents=True, exist_ok=True)
        for f in ("temporal.db", "temporal.db-wal", "temporal.db-shm"):
            (self.dir / f).unlink(missing_ok=True)
        self._spawn(
            [
                TEMPORAL_BIN,
                "server",
                "start-dev",
                "--ip",
                "127.0.0.1",
                "--port",
                "7233",
                "--ui-port",
                "8233",
                "--db-filename",
                str(self.dir / "temporal.db"),
                "--log-level",
                "warn",
            ],
            "temporal.log",
            self.server_pid,
        )

    def start_worker(self) -> None:
        """Start the demo worker in the background."""
        self._spawn(
            [sys.executable, "-m", "undertaker.demo.worker", ADDRESS], "worker.log", self.worker_pid
        )

    async def _connect(self, timeout: float = 30) -> Client:
        end = time.monotonic() + timeout
        while True:
            try:
                client = await Client.connect(ADDRESS)
                await client.count_workflows()
                return client
            except Exception:
                if time.monotonic() > end:
                    raise
                await asyncio.sleep(0.5)

    async def up(self) -> dict:
        """Start everything, seed the scenarios, and write the manifest."""
        if self._alive(self.server_pid) or self._alive(self.worker_pid):
            raise SystemExit("The demo is already up. Run `undertaker demo down` first.")
        self.start_server()
        client = await self._connect()
        changed = await seed_changed_code(client)
        self.start_worker()
        await asyncio.sleep(1)
        if not self._alive(self.worker_pid):
            self.down()
            raise SystemExit(f"The demo worker did not start; see {self.dir / 'worker.log'}")
        await seed_rest(client)
        manifest = dict(MANIFEST)
        if not changed:
            manifest.pop("order-1047")
        out = {
            "seeded_at": datetime.now(UTC).isoformat(),
            "address": ADDRESS,
            "expected": manifest,
            "completed": COMPLETED,
        }
        (self.dir / "manifest.json").write_text(json.dumps(out, indent=2))
        return out

    def down(self) -> list[str]:
        """Stop the worker and the server; return what was stopped."""
        stopped = []
        if self._stop(self.worker_pid):
            stopped.append("worker")
        if self._stop(self.server_pid):
            stopped.append("temporal dev server")
        return stopped

    def status(self) -> dict:
        """Pids of the running parts."""
        return {
            "temporal": self._alive(self.server_pid),
            "worker": self._alive(self.worker_pid),
            "address": ADDRESS,
            "ui": "http://127.0.0.1:8233",
            "temporal_bin": TEMPORAL_BIN if shutil.which(TEMPORAL_BIN) else None,
        }
