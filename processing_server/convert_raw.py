from pathlib import Path
import exiftool
import rawpy
import lensfunpy
import cv2
import numpy as np
from .logging import logger


def is_raw(file_path):
    raw_types = [
        "3FR",
        "ARI",
        "ARW",
        "BAY",
        "BMQ",
        "CAP",
        "CINE",
        "CR2",
        "CR3",
        "CRW",
        "CS1",
        "DC2",
        "DCR",
        "GPR",
        "ERF",
        "FFF",
        "EXR",
        "IA",
        "IIQ",
        "K25",
        "KC2",
        "KDC",
        "MDC",
        "MEF",
        "MOS",
        "MRW",
        "NEF",
        "NRW",
        "ORF",
        "PEF",
        "PFM",
        "PXN",
        "QTK",
        "RAF",
        "RAW",
        "RDC",
        "RW1",
        "RW2",
        "SR2",
        "SRF",
        "SRW",
        "STI",
        "X3F",
    ]

    if Path(file_path).suffix.replace(".", "").upper() in raw_types:
        return True
    return False


def convert_raw_image(image_path, output_path):
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(image_path)[0]
    logger.info(f"Metadata loaded for {image_path}")
    with rawpy.imread(image_path) as raw:
        logger.info(f"Image loaded for {image_path}")
        params = rawpy.Params(
            use_camera_wb=True,
            gamma=(2.222, 4.5),
            no_auto_bright=True,
            output_bps=8,
            output_color=rawpy.ColorSpace.sRGB,
        )
        rgb_image = raw.postprocess(params)
        logger.info(f"Raw conversion complete {image_path}")
        rgb_image = correct_lens_distortion(rgb_image, metadata)
        logger.info(f"Lens Distortion Corrected {image_path}")
        # rgb_image = rgb_image.astype("float32")
        # output_path = Path(output_path).with_suffix(".exr")
        bgr_image = cv2.cvtColor(rgb_image, code=cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, bgr_image, [cv2.IMWRITE_PNG_COMPRESSION, 5])
        logger.info(f"Image written to {output_path}")


def get_cam(metadata):
    db = lensfunpy.Database()
    cam = db.find_cameras(get_camera_make(metadata), get_camera_model(metadata))
    if not len(cam):
        raise Exception("No valid camera models found!")
    return cam[0]


def get_lens(metadata, cam):
    db = lensfunpy.Database()
    lens = db.find_lenses(cam, get_lens_make(metadata), get_lens_model(metadata))
    if not len(lens):
        raise Exception("No valid lens models found!")
    return lens[0]


def correct_lens_distortion(image, metadata):
    cam = get_cam(metadata)
    lens = get_lens(metadata, cam)
    focal_length = get_focal_length(metadata)
    aperture = get_aperture(metadata)
    distance = get_focus_distance(metadata)
    height = image.shape[0]
    width = image.shape[1]

    mod = lensfunpy.Modifier(lens, cam.crop_factor, width, height)
    pixel_format = getattr(np, image.dtype.name)
    mod.initialize(focal_length, aperture, distance, pixel_format=pixel_format)

    undistort_coords = mod.apply_geometry_distortion()
    img_undistorted = cv2.remap(image, undistort_coords, None, cv2.INTER_LANCZOS4)

    return img_undistorted


def get_camera_make(metadata):
    return metadata["EXIF:Make"]


def get_camera_model(metadata):
    return metadata["EXIF:Model"]


def get_lens_make(metadata):
    return metadata["EXIF:LensMake"]


def get_lens_model(metadata):
    return metadata["EXIF:LensModel"]


def get_focal_length(metadata):
    return metadata["EXIF:FocalLength"]


def get_aperture(metadata):
    return metadata["Composite:Aperture"]


def get_focus_distance(metadata):
    return metadata["Composite:HyperfocalDistance"]


def convert_raw(files):
    converted_files = []

    for file in files:
        if is_raw(file):
            output_path = (
                Path(file).parent.parent / "convert_raw" / (Path(file).stem + ".png")
            )
            logger.info(f"Converting raw image {file} to {output_path}")
            output_path.parent.mkdir(exist_ok=True, parents=True)
            convert_raw_image(file, output_path.as_posix())
            converted_files.append(output_path.as_posix())
        else:
            converted_files.append(file)
    return converted_files
