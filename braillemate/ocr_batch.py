"""Run Tesseract OCR over every image under "OCR data/" and save the text.

Output mirrors the input folder structure under "ocr_out/", with one .txt
file per image.

Usage:
    python3 ocr_batch.py [--input-dir "OCR data"] [--output-dir ocr_out]
"""

import argparse
from pathlib import Path

import pytesseract
from PIL import Image

BASE_DIR = Path(__file__).parent
IN_ROOT = BASE_DIR / "OCR data"  # contains FUNSD and Tobacco800
OUT_ROOT = BASE_DIR / "ocr_out"

supported = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

DEFAULT_CONFIG = "--oem 3 --psm 6"


def is_image(path: Path) -> bool:
    """Return True for supported image files, skipping macOS "._" metadata files."""
    return path.suffix.lower() in supported and not path.name.startswith("._")


def find_images(in_root: Path) -> list[Path]:
    """Return every supported image under in_root (recursively), sorted."""
    return sorted(p for p in in_root.rglob("*") if p.is_file() and is_image(p))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch OCR every image in a folder tree.")
    p.add_argument("--input-dir", type=Path, default=IN_ROOT,
                   help='Folder of images to OCR (default: "OCR data" next to this script).')
    p.add_argument("--output-dir", type=Path, default=OUT_ROOT,
                   help="Folder for .txt output (default: ocr_out next to this script).")
    p.add_argument("--config", default=DEFAULT_CONFIG,
                   help=f'Tesseract config string (default: "{DEFAULT_CONFIG}").')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    in_root, out_root = args.input_dir, args.output_dir
    out_root.mkdir(exist_ok=True, parents=True)

    # recursively find images anywhere under the input folder
    image_paths = find_images(in_root)

    if not image_paths:
        print(f"No images found under '{in_root}/'. Check dataset paths.")
    else:
        print(f"Found {len(image_paths)} images. Starting OCR...\n")

    for img_path in image_paths:
        try:
            # Mirror the input folder structure under ocr_out/
            rel = img_path.relative_to(in_root)  # e.g., FUNSD/dataset/training_data/images/xxx.png
            out_dir = out_root / rel.parent
            out_dir.mkdir(parents=True, exist_ok=True)
            out_txt = out_dir / f"{img_path.stem}.txt"

            img = Image.open(img_path)
            text = pytesseract.image_to_string(img, lang="eng", config=args.config)
            out_txt.write_text(text, encoding="utf-8")
            print(f"✓ {rel}")
        except Exception as e:
            print(f"✗ {img_path}: {e}")


if __name__ == "__main__":
    main()
