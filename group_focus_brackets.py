from pathlib import Path
from typing import Dict, List
import shutil


def get_prefix(filepath: Path):
    return filepath.stem.rsplit("_", 1)[0]


def make_group_folder(root_dir, prefix):
    Path(root_dir, prefix).mkdir(exist_ok=True, parents=True)


def sort_photos(path):
    jpgs = Path(path).glob("*.jpg")

    sorted_jpgs = {}

    for jpg in jpgs:
        prefix = get_prefix(jpg)
        if prefix not in sorted_jpgs:
            sorted_jpgs[prefix] = []
        sorted_jpgs[prefix].append(jpg)
    return sorted_jpgs


def move_sorted_photos(sorted_photos: Dict[str, List[Path]]):
    for prefix, jpgs in sorted_photos.items():
        root_dir = jpgs[0].parent
        make_group_folder(root_dir, prefix)
        for jpg in jpgs:
            shutil.move(jpg, Path(root_dir, prefix, jpg.name))


if __name__ == "__main__":
    move_sorted_photos(sort_photos(r"C:\Users\nate\sandbox\lily-001"))
