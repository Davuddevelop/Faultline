"""The runner's loop: register, wait for work, run it, report, repeat.

A heartbeat thread renews the lease while a job runs and relays two signals
back to the work: the campaign was canceled, or the lease was lost. Ctrl-C
(or SIGTERM from a service manager) hands the current job back to the queue
as retryable, so another runner can take it, and exits; a second Ctrl-C
exits at once.
"""

from __future__ import annotations

import os
import platform
import signal
import socket
import threading
import time
import traceback
from typing import Any

import faultline
from faultline import sim_environment
from faultline.config import ConfigError

from . import __version__
from .client import ApiError, Client, LeaseLost
from .config import RunnerConfig, RunnerConfigError
from .execute import Control, Log, Stopped, execute


class Agent:
    def __init__(self, api: str, token: str, cfg: RunnerConfig, *, name: str | None = None,
                 log: Log = print) -> None:
        self.api, self.token, self.cfg = api, token, cfg
        self.name = name or cfg.name
        self.log = log
        self.client = Client(api, token)
        self.stopping = threading.Event()

    def register(self) -> dict:
        info = self.client.register(
            name=self.name, cores=os.cpu_count() or 1,
            host={"hostname": socket.gethostname(), "platform": platform.platform(),
                  "machine": platform.machine()},
            versions={**sim_environment(), "harness": faultline.__version__, "runner": __version__},
            robots=sorted(self.cfg.robots), policies=sorted(self.cfg.policies))
        self.log(f"registered as {self.name!r} with {self.api}: robots {', '.join(info['robots'])}; "
                 f"policies {', '.join(info['policies'])}")
        return info

    def _heartbeat(self, job: str, lease_s: float, control: Control, done: threading.Event) -> None:
        client = Client(self.api, self.token, retries=2)
        try:
            while not done.wait(max(1.0, lease_s / 3)):
                try:
                    r = client.heartbeat(job, dict(control.progress))
                    if r.get("cancel"):
                        control.cancel.set()
                except LeaseLost:
                    control.lost.set()
                    return
                except ApiError as exc:
                    self.log(f"heartbeat failed ({exc}); will retry until the lease runs out")
        finally:
            client.close()

    def run_job(self, job: dict[str, Any]) -> str:
        """Run one claimed job. Returns how it ended."""
        jid, ref = job["job"]["id"], job["campaign"]["ref"]
        control, done = Control(), threading.Event()
        if self.stopping.is_set():
            control.shutdown.set()
        hb = threading.Thread(target=self._heartbeat, args=(jid, float(job["job"]["lease_s"]), control, done),
                              daemon=True)
        hb.start()
        watch = threading.Thread(target=lambda: (self.stopping.wait(), control.shutdown.set()), daemon=True)
        watch.start()
        self.log(f"{ref}: claimed (attempt {job['job']['attempt']})")
        try:
            out = execute(self.client, job, self.cfg, control, self.log)
            self.log(f"{ref}: done, {out.get('failures')} violation(s), {out.get('modes_found')} mode(s)")
            return "done"
        except Stopped as s:
            if s.reason == "canceled":
                self._fail(jid, "canceled at a user's request", canceled=True)
                self.log(f"{ref}: canceled")
            elif s.reason == "shutdown":
                self._fail(jid, f"runner {self.name} stopped mid-campaign; handed back to the queue", retryable=True)
                self.log(f"{ref}: handed back to the queue")
            else:
                self.log(f"{ref}: lease lost, another runner has it now; dropped")
            return s.reason
        except LeaseLost:
            self.log(f"{ref}: lease lost, another runner has it now; dropped")
            return "lease_lost"
        except (ConfigError, RunnerConfigError) as exc:
            self._fail(jid, str(exc))
            self.log(f"{ref}: cannot run: {exc}")
            return "failed"
        except Exception as exc:                       # anything else: report it, don't die
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-8000:]
            self._fail(jid, f"runner error: {exc}\n\n{detail}")
            self.log(f"{ref}: failed: {exc}")
            return "failed"
        finally:
            done.set()

    def _fail(self, jid: str, error: str, **kw) -> None:
        try:
            self.client.fail(jid, error, **kw)
        except (LeaseLost, ApiError) as exc:
            self.log(f"could not report the failure ({exc}); the lease will expire and the job return")

    def run_forever(self, *, once: bool = False, wait_s: float = 20.0) -> int:
        def on_signal(signum, _frame):
            if self.stopping.is_set():
                raise KeyboardInterrupt
            self.log("stopping: finishing the handover; press Ctrl-C again to quit now")
            self.stopping.set()

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, on_signal)
            signal.signal(signal.SIGTERM, on_signal)
        for note in self.cfg.notes:
            self.log(f"note: {note}")
        self.register()
        backoff = 1.0
        while not self.stopping.is_set():
            try:
                job = self.client.claim(wait_s=wait_s)
                backoff = 1.0
            except ApiError as exc:
                self.log(f"cannot reach the control plane ({exc}); retrying in {backoff:.0f} s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue
            if job is None:
                if once:
                    return 0
                self.stopping.wait(self.client.retry_after)      # wakes early on Ctrl-C
                continue
            self.run_job(job)
            if once:
                return 0
        return 0
