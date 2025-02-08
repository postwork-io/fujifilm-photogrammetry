from typing import List
from pathlib import Path
import shutil
from threading import Thread, Event
import queue
import atexit

from .logging import logger
from .convert_raw import convert_raw
from .focus_stack_process import focus_stack_process

PROCESSORS = {"convert_raw": convert_raw, "focus_stack": focus_stack_process}
DEFAULT_POST_PROCESSES = ["convert_raw", "focus_stack"]
TASK_QUEUE = queue.Queue()
THREAD_WORKERS: List["Worker"] = []


class Worker(Thread):
    def __init__(
        self, group=None, target=None, name=None, args=[], kwargs=None, *, daemon=None
    ):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self._stopped = Event()

    def run(self):
        logger.info(f"Starting thread: {self.name}")
        while not self.stopped:
            try:
                data = TASK_QUEUE.get(timeout=1)
                files = data["files"]
                post_process_names = data["post_processes"] or DEFAULT_POST_PROCESSES
                job_name = data["job_name"]
                logger.info(f"Running {', '.join(post_process_names)} for {job_name}")
                for post_process_name in post_process_names:
                    post_process = PROCESSORS.get(post_process_name)
                    if post_process:
                        logger.info(f"Executing {post_process_name}")
                        files = post_process(files)

                for file in files:
                    final_path = Path(
                        Path(file).parent.parent, "final", Path(file).name
                    )
                    Path(final_path).parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy(file, final_path)

            except queue.Empty:
                pass

    def stop(self):
        self._stopped.set()

    @property
    def stopped(self):
        return self._stopped.is_set()


for x in range(1):
    thread = Worker()
    THREAD_WORKERS.append(thread)
    thread.start()


@atexit.register
def cleanup_threads():
    logger.info("Cleaning Up Threads")
    for thread in THREAD_WORKERS:
        thread.stop()
    for thread in THREAD_WORKERS:
        if thread.is_alive():
            thread.join()
