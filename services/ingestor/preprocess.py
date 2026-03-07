"""
PDF Preprocessing Pipeline for Intelli-Credit.
Extracts page images, deskews, normalizes DPI, and detects tables.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class PreprocessedPage:
    """Result of preprocessing a single page."""
    page_number: int
    original_image_path: str
    preprocessed_image_path: str
    width: int = 0
    height: int = 0
    dpi: int = 300
    tables_detected: int = 0
    table_regions: list[dict] = field(default_factory=list)


@dataclass
class PreprocessResult:
    """Result of preprocessing an entire document."""
    source_file: str
    total_pages: int = 0
    pages: list[PreprocessedPage] = field(default_factory=list)
    table_csvs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def extract_page_images(pdf_path: str, output_dir: str) -> list[str]:
    """Extract page images from PDF using poppler's pdftoppm."""
    os.makedirs(output_dir, exist_ok=True)
    result = subprocess.run(
        ["pdftoppm", "-png", "-r", "300", pdf_path, os.path.join(output_dir, "page")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr}")

    images = sorted(Path(output_dir).glob("page-*.png"))
    return [str(p) for p in images]


def preprocess_image(image_path: str, output_path: Optional[str] = None) -> str:
    """Deskew, denoise, and normalize DPI of a page image."""
    import cv2
    import numpy as np

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold for binarization
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Denoise
    denoised = cv2.fastNlMeansDenoising(thresh, h=10)

    # DPI normalization: target ~300 DPI (letter-width ~2550px)
    h, w = denoised.shape
    if w < 2000:
        scale = 2550.0 / w
        new_w = int(w * scale)
        new_h = int(h * scale)
        denoised = cv2.resize(denoised, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    if output_path is None:
        output_path = image_path.replace('.png', '_preprocessed.png')

    cv2.imwrite(output_path, denoised)
    return output_path


def extract_tables_camelot(pdf_path: str, output_dir: str) -> list[str]:
    """Extract tables from PDF using Camelot. Returns list of CSV paths."""
    csv_paths = []
    try:
        import camelot
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
        if len(tables) == 0:
            tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')

        for i, table in enumerate(tables):
            csv_path = os.path.join(output_dir, f"table_{i:03d}.csv")
            table.to_csv(csv_path)
            csv_paths.append(csv_path)
    except ImportError:
        # Camelot not installed, try tabula
        csv_paths = extract_tables_tabula(pdf_path, output_dir)
    except Exception:
        csv_paths = extract_tables_tabula(pdf_path, output_dir)

    return csv_paths


def extract_tables_tabula(pdf_path: str, output_dir: str) -> list[str]:
    """Fallback: Extract tables using Tabula."""
    csv_paths = []
    try:
        import tabula
        tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        for i, df in enumerate(tables):
            csv_path = os.path.join(output_dir, f"table_{i:03d}.csv")
            df.to_csv(csv_path, index=False)
            csv_paths.append(csv_path)
    except Exception:
        pass
    return csv_paths


def preprocess_document(pdf_path: str, work_dir: Optional[str] = None) -> PreprocessResult:
    """Full preprocessing pipeline for a PDF document."""
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="intelli_preprocess_")

    result = PreprocessResult(source_file=pdf_path)
    img_dir = os.path.join(work_dir, "images")
    table_dir = os.path.join(work_dir, "tables")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(table_dir, exist_ok=True)

    # Step 1: Extract page images
    try:
        images = extract_page_images(pdf_path, img_dir)
        result.total_pages = len(images)
    except Exception as e:
        result.errors.append(f"Image extraction failed: {e}")
        return result

    # Step 2: Preprocess each page image
    for i, img_path in enumerate(images):
        try:
            preprocessed = preprocess_image(img_path)
            page = PreprocessedPage(
                page_number=i + 1,
                original_image_path=img_path,
                preprocessed_image_path=preprocessed,
            )
            result.pages.append(page)
        except Exception as e:
            result.errors.append(f"Page {i+1} preprocessing failed: {e}")

    # Step 3: Extract tables
    try:
        result.table_csvs = extract_tables_camelot(pdf_path, table_dir)
    except Exception as e:
        result.errors.append(f"Table extraction failed: {e}")

    return result
