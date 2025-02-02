from pathlib import Path
import subprocess
import os
import cv2
from focus_stack import FocusStacker


def collect_stack_folders(path):
    folders = [
        x for x in Path(path).iterdir() if x.is_dir() and not x.name.startswith(".")
    ]

    return folders


def focus_stack_manager(folders, output_extension=".jpg"):
    stacker = FocusStacker(laplacian_kernel_size=5, gaussian_blur_kernel_size=5)
    for folder in folders:
        image_files = [x.as_posix() for x in folder.glob("*.jpg")]
        stacked = stacker.focus_stack(image_files)
        output_file = Path(folder.parent, folder.name + output_extension)
        cv2.imwrite(output_file.as_posix(), stacked)


if __name__ == "__main__":
    current_dir = Path(r"C:\Users\nate\sandbox\images\full-test")
    folders = collect_stack_folders(current_dir)
    focus_stack_manager(folders=folders)
