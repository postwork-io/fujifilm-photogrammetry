from typing import List
from pathlib import Path
import shutil
from threading import Event
import multiprocessing
import queue
import atexit

from .logging_utils import logger
from .convert_raw import convert_raw
from .focus_stack_process import focus_stack_process
from .extract_specular_map import extract_specular

PROCESSORS = {
    "convert_raw": convert_raw,
    "focus_stack": focus_stack_process,
    "extract_specular": extract_specular,
}
DEFAULT_POST_PROCESSES = ["convert_raw", "focus_stack", "extract_specular"]


class WorkerPool:

    def __init__(self, worker_count=5):
        self.worker_count = worker_count
        self.workers = []
        self._queue = multiprocessing.Queue()

    def add_to_pool(self, data):
        self._queue.put(data)

    def start(self):
        if len(self.workers):
            raise Exception("Pool already has members")
        for x in range(self.worker_count):
            worker = Worker(queue=self._queue)
            self.workers.append(worker)
            worker.start()
        atexit.register(self.stop)

    def stop(self):
        for worker in self.workers:
            if worker.is_alive():
                worker.stop()
                worker.join()
        for worker in self.workers:
            del worker
        self.workers = []


class Worker(multiprocessing.Process):
    def __init__(
        self,
        queue=None,
    ):
        super().__init__()
        self._stopped = Event()
        self._queue = queue

    def run(self):
        logger.info(f"Starting thread: {self.name}")
        while not self.stopped:
            try:
                data = self._queue.get(timeout=1)
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
        del self._target, self._args, self._kwargs

    def stop(self):
        self._stopped.set()

    @property
    def stopped(self):
        return self._stopped.is_set()
