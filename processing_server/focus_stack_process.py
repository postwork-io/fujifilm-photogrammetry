from pathlib import Path
import cv2
from focus_stack import FocusStacker


def focus_stack_process(files, extension=".png"):
    if not len(files):
        return files
    root_dir = Path(
        Path(files[0]).parent.parent,
        "focus_stack",
    )
    # {job name}_{capture number}_{focus bracket number}
    name = Path(files[0]).stem.rsplit("_", 1)[0]
    stacker = FocusStacker(laplacian_kernel_size=5, gaussian_blur_kernel_size=5)
    stacked = stacker.focus_stack(files)
    output_file = Path(root_dir, name + extension)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    cv2.imwrite(output_file.as_posix(), stacked)
    return [output_file.as_posix()]
