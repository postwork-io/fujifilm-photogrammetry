from pathlib import Path
from scipy.optimize import curve_fit
import numpy as np

try:
    import gphoto2 as gp
except ImportError:
    gp = None

from .const import lenses, settings


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


def lens_model(x, a, b):
    return a * np.log(x) + b


def capture_focus_bracket(
    camera,
    local_path,
    focus_settings=settings.FOCUS_DISTANCE,
    start_distance=0.3,
    end_distance=0.4,
    steps=5,
    lens=lenses.x35mm,
    model=lens_model,
):
    base_filename = Path(local_path).name

    for idx, rotation_value in enumerate(
        get_rotation_values(start_distance, end_distance, steps, lens, model)
    ):
        bracket_filename = f"{base_filename}_{str(idx).zfill(3)}"
        bracket_filepath = Path(local_path).with_name(bracket_filename).as_posix()
        change_camera_setting(camera, focus_settings, str(rotation_value))
        capture_image(camera, bracket_filepath)


def get_mapping_function(lens, model=lens_model):
    focus_distance, rotation = lens
    params, _ = curve_fit(model, np.array(focus_distance), np.array(rotation))
    a, b = params
    return lambda x: model(x, a, b)


def get_rotation_values(
    start_distance=0.3, end_distance=0.4, steps=5, lens=lenses.x35mm, model=lens_model
):
    mapping_function = get_mapping_function(lens, model)
    step_size = (end_distance - start_distance) / steps
    step_values = [start_distance + x + step_size for x in range(steps)]
    return [int(mapping_function(x)) for x in step_values]
