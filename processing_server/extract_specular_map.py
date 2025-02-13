from pathlib import Path
import cv2


def sort_files(files):
    diffuse = []
    spec = []

    for file in files:
        if Path(file).stem.lower().endswith("_spec"):
            spec.append(file)
        else:
            diffuse.append(file)
    diffuse.sort()
    spec.sort()
    return diffuse, spec


def extract_specular_from_images(diffuse_image, combined_image, output_path):
    diffuse = cv2.imread(diffuse_image)
    combined = cv2.imread(combined_image)

    spec = cv2.subtract(combined, diffuse)

    spec_gray = cv2.cvtColor(spec, cv2.COLOR_BGR2GRAY)

    cv2.imwrite(output_path, spec_gray)


def extract_specular(files):
    diffuse, spec = sort_files(files)

    if not spec:
        return files
    output_root_path = Path(files[0]).parent.parent / "extract_specular"
    output_root_path.mkdir(exist_ok=True, parents=True)
    processed_file_paths = []
    for diffuse_file_path, specular_file_path in zip(diffuse, spec):
        processed_file_paths.append(diffuse_file_path)
        output_file_path = Path(
            output_root_path, Path(specular_file_path).name
        ).as_posix()

        extract_specular_from_images(
            diffuse_file_path, specular_file_path, output_file_path
        )
        processed_file_paths.append(output_file_path)
    return processed_file_paths


if __name__ == "__main__":
    result = extract_specular(
        ["sandbox/convert_raw/DSCF9601.png", "sandbox/convert_raw/DSCF9602_spec.png"]
    )
    pass
