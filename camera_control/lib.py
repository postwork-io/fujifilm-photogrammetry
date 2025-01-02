from pathlib import Path
import time
import threading
import subprocess

from PIL import Image

try:
    import gphoto2 as gp
except ImportError:
    gp = None

from .const import settings
from .settings import THUMBNAIL_SIZE


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


def capture_image(camera, local_path, thumbnail=True):
    """Capture an image and save it to a file."""
    # Trigger the capture
    file_path = gp.check_result(gp.gp_camera_capture(camera, gp.GP_CAPTURE_IMAGE))
    print("Image captured:", file_path.name)

    # Download the image
    local_path = Path(local_path).with_suffix(Path(file_path.name).suffix).as_posix()
    camera_file = gp.check_result(
        gp.gp_camera_file_get(
            camera, file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL
        )
    )
    gp.check_result(gp.gp_file_save(camera_file, local_path))
    time.sleep(0.5)
    print("Image saved as:", local_path)
    if thumbnail:
        thumbnail_path = Path(local_path).parent / ".thumbnails" / Path(local_path).name
        thumbnail_path.parent.mkdir(exist_ok=True, parents=True)
        im = Image.open(local_path)
        im.thumbnail(THUMBNAIL_SIZE)
        im.save(thumbnail_path)
        print("Thumbnail saved as:", thumbnail_path.as_posix())


def capture_focus_bracket(
    camera,
    local_path,
    focus_settings=settings.FOCUS_DISTANCE,
    focus_start=1730,
    focus_stop=1500,
    focus_steps=5,
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
        capture_image(camera, bracket_filepath)
        yield ((step + 1) / focus_steps)


def bulk_capture(
    capture_root_dir="~/captures",
    capture_name="untitled",
    image_count=60,
    start_number=1,
    focus_bracket_settings=None,
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

            if focus_bracket_settings is not None:
                for completion in capture_focus_bracket(
                    camera, capture_path, **focus_bracket_settings
                ):
                    base_completion = float(idx) / float(image_count)
                    percent_complete = base_completion + (main_step_size * completion)
                    yield Path(capture_path).name, percent_complete
            else:
                percent_complete = float(idx + 1) / float(image_count)
                capture_image(camera, capture_path)
                yield Path(capture_path).name, percent_complete
            if callback:
                callback(capture_path)


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


class StoppableThread(threading.Thread):
    def __init__(
        self, group=None, target=None, name=None, args=[], kwargs={}, *, daemon=None
    ):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self._stop_event = threading.Event()
        self._status = ("not started", 0.0)

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

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
