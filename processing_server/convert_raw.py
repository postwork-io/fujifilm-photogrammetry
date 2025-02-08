import subprocess
from pathlib import Path


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


def convert_raw(files):
    converted_files = []
    img_format = "png"
    settings = [("bpp", 8), ("compression", 5)]
    for file in files:
        if is_raw(file):
            output_path = (
                Path(file).parent.parent / "convert_raw" / Path(file).stem + ".png"
            )
            args = [
                "darktable-cli",
                str(file),
                str(output_path),
            ]
            if settings:
                args.append("--core")
                args.append("--conf")
            for option, value in settings:
                args.append(f"plugins/imageio/format/{img_format}/{option}={value}")
            proc = subprocess.Popen(args)
            proc.wait()
        else:
            converted_files.append(file)
    return converted_files
