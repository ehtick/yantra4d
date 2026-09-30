"""
Shared Render Engine Utilities
Provides common process management for OpenSCAD and CadQuery render engines.
Both engines share: RENDER_TIMEOUT_S, active-process tracking, and cancel logic.
"""
import logging
import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

RENDER_TIMEOUT_S = int(os.getenv("RENDER_TIMEOUT_S", "300"))


@dataclass
class RenderResult:
    """Structured result from a render subprocess.

    Supports tuple unpacking for backward compatibility:
        success, stderr = run_render(cmd)
    """
    success: bool
    stderr: str
    output_path: str | None = None
    duration_ms: float | None = None

    def __iter__(self):
        """Allow ``success, stderr = result`` unpacking."""
        yield self.success
        yield self.stderr


class ProcessManager:
    """Thread-safe tracker for a single active render subprocess.

    Usage:
        pm = ProcessManager()
        process = pm.start(subprocess.Popen(...))
        # later…
        pm.cancel()
    """

    def __init__(self):
        self._active_process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def start(self, process: subprocess.Popen) -> subprocess.Popen:
        """Register *process* as the current active render and return it."""
        with self._lock:
            self._active_process = process
        return process

    def clear(self) -> None:
        """Deregister the active process (call after it finishes)."""
        with self._lock:
            self._active_process = None

    def cancel(self) -> bool:
        """Terminate the active process if one is running.

        Returns True if a process was cancelled, False if none was active.
        """
        with self._lock:
            proc = self._active_process
            if proc is None or proc.poll() is not None:
                return False
            logger.info("Cancelling active render process (pid=%s)", proc.pid)
            proc.terminate()

        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

        self.clear()
        return True


def communicate_cancellable(
    process: subprocess.Popen,
    is_cancelled: Callable[[], bool],
    cancel: Callable[[], bool],
) -> tuple[str, str | None]:
    """Drain both pipes while retaining cancellation and the caller's deadline.

    Waiting for exit before communicate() deadlocks when a renderer fills its
    stdout/stderr pipe. Repeated timed communicate() calls keep draining and
    retain collected output across TimeoutExpired, while polling cancellation.
    The caller continues to own its kill timer and process-manager cleanup.
    """
    while True:
        if is_cancelled():
            cancel()
        try:
            return process.communicate(timeout=0.05)
        except subprocess.TimeoutExpired:
            continue
