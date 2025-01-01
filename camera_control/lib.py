from pathlib import Path

try:
    import gphoto2 as gp
except ImportError:
    gp = None

from .const import settings


def get_camera():
    context = gp.gp_context_new()
    camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(camera, context))

    return camera


def change_camera_setting(camera, setting_name, value):
    """Change a camera setting."""
    config = gp.check_result(gp.gp_camera_get_config(camera))
    setting = gp.check_result(gp.gp_widget_get_child_by_name(config, setting_name))
    gp.check_result(gp.gp_widget_set_value(setting, value))
    gp.check_result(gp.gp_camera_set_config(camera, config))


def capture_image(camera, local_path):
    """Capture an image and save it to a file."""
    # Trigger the capture
    file_path = gp.check_result(gp.gp_camera_capture(camera, gp.GP_CAPTURE_IMAGE))
    print("Image captured:", file_path)

    # Download the image
    local_path = Path(local_path).with_suffix(Path(file_path.name).suffix).as_posix()
    camera_file = gp.check_result(
        gp.gp_camera_file_get(
            camera, file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL
        )
    )
    gp.check_result(gp.gp_file_save(camera_file, local_path))
    print("Image saved as:", local_path)


def capture_focus_bracket(
    camera,
    local_path,
    focus_settings=settings.FOCUS_DISTANCE,
    start_focus=1730,
    end_focus=1500,
    steps=5,
):
    base_filename = Path(local_path).name
    step_size = (start_focus - end_focus) / steps
    for step in range(steps):
        bracket_filename = f"{base_filename}_{str(step).zfill(3)}"
        bracket_filepath = Path(local_path).with_name(bracket_filename).as_posix()
        change_camera_setting(
            camera, focus_settings, str(int(end_focus + (step_size * step)))
        )
        capture_image(camera, bracket_filepath)
