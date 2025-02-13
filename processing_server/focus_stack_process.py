# -*- coding: utf-8 -*-
"""
This code and algorithm was inspired and adapted from the following sources:
http://stackoverflow.com/questions/15911783/what-are-some-common-focus-stacking-algorithms
https://github.com/cmcguinness/focusstack

"""
import logging
from pathlib import Path
from typing import List, Tuple
import numpy as np
import cv2

logger = logging.getLogger()

DEBUG = False

# use SIFT or ORB for feature detection.
# SIFT generally produces better results, but it is not FOSS (OpenCV 4.X does not support it).
USE_SIFT = True


class FocusStacker(object):
    def __init__(
        self,
        laplacian_kernel_size: int = 5,
        gaussian_blur_kernel_size: int = 5,
    ) -> None:
        """Focus stacking class.
        Args:
            laplacian_kernel_size: Size of the laplacian window. Must be odd.
            gaussian_blur_kernel_size: How big of a kernel to use for the gaussian blur. Must be odd.
        """
        self._laplacian_kernel_size = laplacian_kernel_size
        self._gaussian_blur_kernel_size = gaussian_blur_kernel_size

    def focus_stack(
        self, images: List[np.ndarray]
    ) -> Tuple[np.ndarray, List[np.ndarray], np.ndarray]:
        """Pipeline to focus stack a list of images."""
        alignment_matrices = self._get_alignment_matrices(images)
        images = self._align_images(images, alignment_matrices)
        laplacian = self._compute_laplacian(images)
        mask = self._find_focus_regions(laplacian)
        focus_stacked = self._apply_focus_region(images, mask)
        return focus_stacked, alignment_matrices, mask

    def apply_focus_stacking(
        self,
        images: List[np.ndarray],
        alignment_matrices: List[np.ndarray],
        region_mask: np.ndarray,
    ):
        images = self._align_images(images, alignment_matrices)
        focus_stacked = self._apply_focus_region(images, region_mask)

        return focus_stacked

    @staticmethod
    def load_images(image_files: List[str]) -> List[np.ndarray]:
        """Read the images into numpy arrays using OpenCV."""
        logger.info("reading images")
        return [cv2.imread(img) for img in image_files]

    @staticmethod
    def _get_alignment_matrices(images: List[np.ndarray]) -> List[np.ndarray]:
        """Align the images.  Changing the focus on a lens, even if the camera remains fixed,
         causes a mild zooming on the images. We need to correct the images so they line up perfectly on top
        of each other.

        Args:
            images: list of image data
        """

        def _find_homography(
            _img1_key_points: np.ndarray, _image_2_kp: np.ndarray, _matches: List
        ):
            image_1_points = np.zeros((len(_matches), 1, 2), dtype=np.float32)
            image_2_points = np.zeros((len(_matches), 1, 2), dtype=np.float32)

            for j in range(0, len(_matches)):
                image_1_points[j] = _img1_key_points[_matches[j].queryIdx].pt
                image_2_points[j] = _image_2_kp[_matches[j].trainIdx].pt

            homography, mask = cv2.findHomography(
                image_1_points, image_2_points, cv2.RANSAC, ransacReprojThreshold=2.0
            )

            return homography

        logger.info("aligning images")
        aligned_imgs = []

        detector = cv2.xfeatures2d.SIFT_create() if USE_SIFT else cv2.ORB_create(1000)

        # Assume that image 0 is the "base" image and align all the following images to it
        aligned_imgs.append(images[0])
        img0_gray = cv2.cvtColor(images[0], cv2.COLOR_BGR2GRAY)
        img1_key_points, image1_desc = detector.detectAndCompute(img0_gray, None)

        alignment_matrices = []

        for i in range(1, len(images)):
            img_i_key_points, image_i_desc = detector.detectAndCompute(images[i], None)

            if USE_SIFT:
                bf = cv2.BFMatcher()
                # This returns the top two matches for each feature point (list of list)
                pair_matches = bf.knnMatch(image_i_desc, image1_desc, k=2)
                raw_matches = []
                for m, n in pair_matches:
                    if m.distance < 0.7 * n.distance:
                        raw_matches.append(m)
            else:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                raw_matches = bf.match(image_i_desc, image1_desc)

            sort_matches = sorted(raw_matches, key=lambda x: x.distance)
            matches = sort_matches[0:128]

            homography_matrix = _find_homography(
                img_i_key_points, img1_key_points, matches
            )
            alignment_matrices.append(homography_matrix)
        return alignment_matrices

    def _align_images(
        self, images: List[np.ndarray], alignment_matrices: List[np.ndarray]
    ):
        aligned_imgs = []
        i = 0
        for image, alignement_matrix in zip(images, alignment_matrices):
            aligned_img = cv2.warpPerspective(
                image,
                alignement_matrix,
                (image.shape[1], image.shape[0]),
                flags=cv2.INTER_LINEAR,
            )

            aligned_imgs.append(aligned_img)
            if DEBUG:
                # If you find that there's a large amount of ghosting,
                # it may be because one or more of the input images gets misaligned.
                cv2.imwrite(f"aligned_{i}.png", aligned_img)
            i += 1
        return aligned_imgs

    def _compute_laplacian(
        self,
        images: List[np.ndarray],
    ) -> np.ndarray:
        """Gaussian blur and compute the gradient map of the image. This is proxy for finding the focus regions.

        Args:
            images: image data
        """
        logger.info("Computing the laplacian of the blurred images")
        laplacians = []
        for image in images:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(
                gray,
                (self._gaussian_blur_kernel_size, self._gaussian_blur_kernel_size),
                0,
            )
            laplacian_gradient = cv2.Laplacian(
                blurred, cv2.CV_64F, ksize=self._laplacian_kernel_size
            )
            laplacians.append(laplacian_gradient)
        laplacians = np.asarray(laplacians)
        logger.debug(f"Shape of array of laplacian gradient: {laplacians.shape}")
        return laplacians

    @staticmethod
    def _find_focus_regions(laplacian_gradient: np.ndarray) -> np.ndarray:
        """Take the absolute value of the Laplacian (2nd order gradient) of the Gaussian blur result.
        This will quantify the strength of the edges with respect to the size and strength of the kernel (focus regions).

        Then create a blank image, loop through each pixel and find the strongest edge in the LoG
        (i.e. the highest value in the image stack) and take the RGB value for that
        pixel from the corresponding image.

        Then for each pixel [x,y] in the output image, copy the pixel [x,y] from
        the input image which has the largest gradient [x,y]

        Args:
            images: list of image data to focus and stack.
            laplacian_gradient: the laplacian of the stack. This is the proxy for the focus region.
                Should be size: (len(images), images.shape[0], images.shape[1])

        Returns:
            np.array image data of focus stacked image, size of orignal image

        """
        logger.info("Using laplacian gradient to find regions of focus, and stack.")
        abs_laplacian = np.absolute(laplacian_gradient)
        maxima = abs_laplacian.max(axis=0)
        bool_mask = np.array(abs_laplacian == maxima)
        mask = bool_mask.astype(np.uint8)

        return mask

    @staticmethod
    def _apply_focus_region(images: List[np.ndarray], mask: np.ndarray):
        output = np.zeros(shape=images[0].shape, dtype=images[0].dtype)
        for i, img in enumerate(images):
            output = cv2.bitwise_not(img, output, mask=mask[i])

        return 255 - output


def sort_files(files):
    diffuse = []
    spec = []

    for file in files:
        if Path(file).stem.lower().endswith("_spec"):
            spec.append(file)
        else:
            diffuse.append(file)
    return diffuse, spec


def files_have_spec(diffuse, spec):
    if not len(spec):
        return False
    if len(diffuse) == len(spec):
        return True
    logger.error(
        "Spec files included but do not match the count of diffuse files. "
        "Discarding mismatched specular images."
    )
    return False


def skip_focus_stacking(diffuse, spec):
    if len(diffuse) == 1 and len(spec) <= 1:
        return True
    else:
        return False


def focus_stack_process(files, extension=".png"):
    if not len(files):
        return files
    root_dir = Path(
        Path(files[0]).parent.parent,
        "focus_stack",
    )
    # {job name}_{capture number}_{focus bracket number}
    processed_files = []
    stacker = FocusStacker(laplacian_kernel_size=5, gaussian_blur_kernel_size=5)
    diffuse, spec = sort_files(files)
    name = Path(diffuse[0]).stem.rsplit("_", 1)[0]
    diffuse_images = stacker.load_images(diffuse)
    if skip_focus_stacking(diffuse, spec):
        return files
    stacked, alignment_matrices, mask = stacker.focus_stack(diffuse_images)
    if files_have_spec(diffuse, spec):
        spec_images = stacker.load_images(spec)
        spec_stacked = stacker.apply_focus_stacking(
            spec_images, alignment_matrices, mask
        )
        spec_output_file = Path(root_dir, f"{name}_spec{extension}")
        cv2.imwrite(spec_output_file.as_posix(), spec_stacked)
        processed_files.append(spec_output_file.as_posix())
    diffuse_output_file = Path(root_dir, name + extension)
    diffuse_output_file.parent.mkdir(exist_ok=True, parents=True)
    cv2.imwrite(diffuse_output_file.as_posix(), stacked)
    processed_files.append(diffuse_output_file.as_posix())
    return processed_files


if __name__ == "__main__":
    result = focus_stack_process(
        ["sandbox/convert_raw/DSCF9601.png", "sandbox/convert_raw/DSCF9602_spec.png"]
    )
    pass
