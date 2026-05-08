"""
Background Queue — Asynchronous task execution for slow indexing processes.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

logger = logging.getLogger(__name__)


class BackgroundQueue:
    """
    Executes heavy tasks (like Graph LLM extraction) in a background thread pool
    so the main REPL remains unblocked.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BackgroundQueue, cls).__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        """Initialize the thread pool executor (singleton)."""
        # A single worker thread prevents LLM rate limits/concurrency issues
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="IndexNote_Worker")
        logger.info("BackgroundQueue initialized")

    def submit(self, fn: Callable[..., Any], *args, **kwargs) -> None:
        """
        Submit a task to be executed in the background.

        Args:
            fn: The function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.
        """
        def _task_wrapper():
            try:
                logger.info("Starting background task: %s", fn.__name__)
                fn(*args, **kwargs)
                logger.info("Finished background task: %s", fn.__name__)
            except Exception as e:
                logger.error("Error in background task %s: %s", fn.__name__, e)

        self._executor.submit(_task_wrapper)

    def shutdown(self):
        """Shutdown the executor gracefully."""
        self._executor.shutdown(wait=False)
