from typing import Optional
from pathlib import Path
import atexit
import json
import mimetypes
import requests
import time
import threading
import subprocess
import queue

from PIL import Image

try:
    import gphoto2 as gp
except ImportError:
    gp = None

from .const import settings
from .settings import (
    THUMBNAIL_SIZE,
    TURNTABLE_STEPPER_PIN,
    POLARIZER_DIRECTION_PIN,
    POLARIZER_STEPPER_PIN,
    TURNTABLE_STEPS_PER_ROTATION,
    POLARIZER_STEPS_PER_ROTATION,
    POST_PROCESS_URL,
    SETTLE_TIME,
)
from .stepper import Stepper

WORKER: Optional["WorkerThread"] = None


class CameraContext(object):
    def __init__(self):
        self.camera = get_camera()

    def __enter__(self):
        return self.camera

    def __exit__(self, type, value, traceback):
        try:
            self.camera.exit()
        except gp.GPhoto2Error:
            time.sleep(2)
            self.camera.exit()


def upload_files(url, job_name, file_paths=[], delete_on_success=True):
    multiple_files = []

    for file_path in file_paths:
        mimetype = mimetypes.guess_type(file_path)[0]
        multiple_files.append(
            ("files", (Path(file_path).name, open(file_path, "rb"), mimetype))
        )
    data = {"job_name": job_name}
    multiple_files.append(("data", ("data", json.dumps(data), "application/json")))
    print("Uploading Files")
    response = requests.post(url, files=multiple_files)

    for file in multiple_files:
        open_file = file[1][1]
        if hasattr(open_file, "close"):
            open_file.close()
    if response.status_code == 200 and delete_on_success:
        for file_path in file_paths:
            Path(file_path).unlink()
    return response


def get_camera():
    context = gp.gp_context_new()
    camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(camera, context))

    return camera


def get_camera_setting(camera, setting_name):
    config = gp.check_result(gp.gp_camera_get_config(camera))
    setting = gp.check_result(gp.gp_widget_get_child_by_name(config, setting_name))
    return gp.check_result(gp.gp_widget_get_value(setting))


def change_camera_setting(camera, setting_name, value):
    """Change a camera setting."""
    config = gp.check_result(gp.gp_camera_get_config(camera))
    setting = gp.check_result(gp.gp_widget_get_child_by_name(config, setting_name))
    gp.check_result(gp.gp_widget_set_value(setting, value))
    gp.check_result(gp.gp_camera_set_config(camera, config))
    print(f"Setting: {setting_name} Set to: {value}")
    time.sleep(0.1)


def capture_image(camera, local_path, thumbnail=True, delete_on_camera=True):
    """Capture an image and save it to a file."""
    # Trigger the capture
    file_path = gp.check_result(gp.gp_camera_capture(camera, gp.GP_CAPTURE_IMAGE))
    print("Image captured:", file_path.name)

    # disable thumbnail if image is not valid for thumbnailing
    if thumbnail and not file_path.name.lower().endswith("jpg"):
        thumbnail = False

    # Download the image
    local_path = Path(local_path).with_suffix(Path(file_path.name).suffix).as_posix()
    camera_file = gp.check_result(
        gp.gp_camera_file_get(
            camera, file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL
        )
    )
    gp.check_result(gp.gp_file_save(camera_file, local_path))
    # remove the file because it is only stored in an image buffer on the xt2 and will lock I/O
    if delete_on_camera:
        gp.check_result(
            gp.gp_camera_file_delete(camera, file_path.folder, file_path.name)
        )
    print("Image saved as:", local_path)
    if thumbnail:
        thumbnail_path = Path(local_path).parent / ".thumbnails" / Path(local_path).name
        thumbnail_path.parent.mkdir(exist_ok=True, parents=True)
        im = Image.open(local_path)
        im.thumbnail(THUMBNAIL_SIZE)
        im.save(thumbnail_path)
        print("Thumbnail saved as:", thumbnail_path.as_posix())
    return local_path


def capture_focus_bracket(
    camera,
    local_path,
    focus_settings=settings.FOCUS_DISTANCE,
    focus_start=1730,
    focus_stop=1500,
    focus_steps=5,
    capture_specular=False,
):
    if int(focus_start) < int(focus_stop):
        tmp_focus_start = focus_stop
        tmp_focus_stop = focus_start
        focus_start = tmp_focus_start
        focus_stop = tmp_focus_stop

    base_filename = Path(local_path).name
    step_size = (focus_start - focus_stop) / ((focus_steps - 1) or 1)
    for step in range(focus_steps):
        bracket_filename = f"{base_filename}_{str(step).zfill(3)}"
        bracket_filepath = Path(local_path).with_name(bracket_filename).as_posix()
        change_camera_setting(
            camera, focus_settings, str(int(focus_stop + (step_size * step)))
        )
        if capture_specular:
            for idx, image in enumerate(
                capture_specular_maps(camera, bracket_filename)
            ):
                yield ((step + 1 + idx) / (focus_steps * 2)), image
        else:
            local_path = capture_image(camera, bracket_filepath)
            yield ((step + 1) / focus_steps), local_path


def capture_specular_maps(camera, filepath):
    diffuse = capture_image(camera, filepath)
    with Stepper(
        POLARIZER_STEPPER_PIN,
        direction_pin=POLARIZER_DIRECTION_PIN,
        cool_down=0,
        steps_per_rotation=POLARIZER_STEPS_PER_ROTATION,
    ) as polarizer_stepper:
        polarizer_stepper.advance_degrees(
            degrees=90, direction=polarizer_stepper.FORWARD
        )
        spec_filepath = Path(
            Path(filepath).parent, Path(filepath).stem + "_spec" + Path(filepath).suffix
        ).as_posix()
        spec = capture_image(camera, spec_filepath)
        polarizer_stepper.advance_degrees(
            degrees=90, direction=polarizer_stepper.REVERSE
        )
    return [diffuse, spec]


def bulk_capture_turntable(
    capture_root_dir="~/captures",
    capture_name="untitled",
    image_count=60,
    start_number=1,
    focus_bracket_settings=None,
    degree_per_capture=6.0,
    capture_specular=False,
):
    with Stepper(
        step_pin=TURNTABLE_STEPPER_PIN,
        steps_per_rotation=TURNTABLE_STEPS_PER_ROTATION,
        cool_down=SETTLE_TIME,
    ) as stepper:

        def callback(captured_images, *args, **kwargs):
            stepper.advance_degrees(degree_per_capture)
            process_function_background(
                lambda: upload_files(POST_PROCESS_URL, capture_name, captured_images)
            )

        yield from bulk_capture(
            capture_root_dir=capture_root_dir,
            capture_name=capture_name,
            image_count=image_count,
            start_number=start_number,
            focus_bracket_settings=focus_bracket_settings,
            capture_specular=capture_specular,
            callback=callback,
        )


def move_turntable(degrees=15.0):
    with Stepper(
        step_pin=TURNTABLE_STEPPER_PIN,
        steps_per_rotation=TURNTABLE_STEPS_PER_ROTATION,
        cool_down=SETTLE_TIME,
    ) as stepper:
        stepper.advance_degrees(degrees)


def bulk_capture(
    capture_root_dir="~/captures",
    capture_name="untitled",
    image_count=60,
    start_number=1,
    focus_bracket_settings=None,
    capture_specular=False,
    callback=None,
):
    image_count = int(image_count)
    start_number = int(start_number)
    main_step_size = 1.0 / float(image_count)
    with CameraContext() as camera:
        for idx in range(image_count):
            image_id = idx + start_number
            capture_path = Path(
                capture_root_dir,
                capture_name,
                f"{capture_name}_{str(image_id).zfill(4)}",
            ).as_posix()
            captured_images = []
            if focus_bracket_settings is not None:
                for completion, local_path in capture_focus_bracket(
                    camera, capture_path, **focus_bracket_settings
                ):
                    base_completion = float(idx) / float(image_count)
                    percent_complete = base_completion + (main_step_size * completion)
                    captured_images.append(local_path)
                    yield Path(capture_path).name, percent_complete
            else:
                if capture_specular:
                    base_percent = float(idx) / float(image_count)
                    for i, image in enumerate(
                        capture_specular_maps(camera, capture_path)
                    ):
                        increment = 0.5 / float(image_count)
                        percent_complete = base_percent + (increment * (1 + i))
                        captured_images.append(image)
                        yield image, percent_complete
                    pass
                else:
                    percent_complete = float(idx + 1) / float(image_count)
                    local_path = capture_image(camera, capture_path)
                    captured_images.append(local_path)
                    yield Path(capture_path).name, percent_complete
            if callback:
                callback(captured_images)


def mock_bulk_capture(
    capture_root_dir="~/captures",
    capture_name="untitled",
    image_count=60,
    start_number=1,
    focus_bracket_settings=None,
    callback=None,
):
    image_count = int(image_count)
    start_number = int(start_number)
    for idx in range(image_count):
        time.sleep(0.1)
        percent_complete = float(idx + 1) / float(image_count)
        yield f"{capture_name} {idx+start_number}", percent_complete


def mount_usb_drive(device_path, mount_path):
    if not Path(device_path).exists():
        raise Exception("No Device to Mount")
    if not Path(mount_path).exists():
        Path(mount_path).mkdir(parents=True)
    subprocess.run(["sudo", "mount", device_path, mount_path])


def list_usb_drives():
    try:
        # Run lsblk to list all block devices
        result = subprocess.run(
            ["lsblk", "-o", "NAME,MODEL,TRAN,SIZE"], capture_output=True, text=True
        )
        drives = [x.strip() for x in result.stdout.splitlines()]

        # Filter for USB devices
        usb_drives = [
            line for line in drives if "usb" in line.lower() and "part" in line.lower()
        ]

        print("Connected USB Drives:")
        for drive in usb_drives:
            print(drive)
        return usb_drives
    except Exception as e:
        print("Error listing USB drives:", e)
        return []


def get_worker_progress():
    global WORKER

    if WORKER and WORKER.is_alive():
        if WORKER._queue.qsize() or WORKER.is_executing_job():
            return {"running": True, "pending_jobs": WORKER._queue.qsize()}

    return {"running": False, "pending_jobs": 0}


def process_function_background(func):
    global WORKER

    if not WORKER or not WORKER.is_alive():

        WORKER = WorkerThread()
        WORKER.start()
    WORKER.add_to_queue(func)


@atexit.register
def cleanup_background_worker():
    global WORKER

    if WORKER:
        WORKER.stop()
        WORKER.join()
        del WORKER


class WorkerThread(threading.Thread):
    def __init__(
        self, group=None, target=None, name=None, args=[], kwargs=None, *, daemon=None
    ):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self._stop_event = threading.Event()
        self._keep_alive = 10.0
        self._executing_job = False
        if kwargs and kwargs.get("queue"):
            self._queue = kwargs["queue"]
        else:
            self._queue = queue.Queue()

    def add_to_queue(self, item):
        self._queue.put(item)

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def is_executing_job(self):
        return self._executing_job

    def run(self):
        while not self.stopped():
            try:
                func = self._queue.get(timeout=1.0)
                print(f"Running {func}")
                self._executing_job = True
                func()

            except queue.Empty:
                pass
            self._executing_job = False

        # Avoid a refcycle if the thread is running a function with
        # an argument that has a member that points to the thread.
        del self._target, self._args, self._kwargs


class StoppableThread(WorkerThread):
    def __init__(
        self, group=None, target=None, name=None, args=[], kwargs=None, *, daemon=None
    ):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self._status = ("not started", 0.0)

    def get_status(self):
        return self._status

    def run(self):
        try:
            if self._target is not None:
                for status in self._target(*self._args, **self._kwargs):
                    self._status = status
                    if self.stopped():
                        break
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs
