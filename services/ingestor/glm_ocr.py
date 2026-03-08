"""
GLM-OCR inference service for Intelli-Credit.
Converts document PDFs/images to structured Markdown with provenance.

Usage:
  python glm_ocr.py --input-dir <dir_with_images> --output-dir <output> --source-file <original.pdf>

Backend priority: PyMuPDF text extraction -> PaddleOCR-VL (GPU) -> Tesseract fallback
"""
import argparse
import base64
import io
import json
import os
import re as _re
import sys
import glob
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://172.23.112.1:11434")
GLM_OCR_MODEL = os.environ.get("GLM_OCR_MODEL", "glm-ocr:bf16")
PADDLE_OCR_MODEL_ID = "strangervisionhf/PaddleOCR-VL-1.5-hf-transformers-v5.2.0.dev0"

OCR_PROMPT = (
    "Convert this document page to structured Markdown. "
    "Preserve all text, tables, numbers, dates, and identifiers exactly. "
    "Use proper Markdown formatting for headings, tables, and lists."
)

# ---------------------------------------------------------------------------
# PaddleOCR-VL singleton (loaded once, reused across calls)
# ---------------------------------------------------------------------------
_paddle_model = None
_paddle_processor = None


def preload_ocr_model():
    """Pre-load PaddleOCR-VL into GPU memory (call once at startup)."""
    global _paddle_model, _paddle_processor
    if _paddle_model is not None:
        return
    try:
        import torch
        from transformers import AutoProcessor
        from transformers.models.paddleocr_vl import PaddleOCRVLForConditionalGeneration

        print(f"[OCR] Loading PaddleOCR-VL model ({PADDLE_OCR_MODEL_ID})...")
        _paddle_processor = AutoProcessor.from_pretrained(PADDLE_OCR_MODEL_ID)
        _paddle_model = PaddleOCRVLForConditionalGeneration.from_pretrained(
            PADDLE_OCR_MODEL_ID,
            dtype=torch.bfloat16,
            device_map="cuda",
        )
        print("[OCR] PaddleOCR-VL loaded successfully.")
    except Exception as e:
        print(f"[OCR] Failed to load PaddleOCR-VL: {e}", file=sys.stderr)
        _paddle_model = None
        _paddle_processor = None


def unload_ocr_model():
    """Free PaddleOCR-VL from GPU memory (call before loading LLM)."""
    global _paddle_model, _paddle_processor
    if _paddle_model is not None:
        del _paddle_model
        _paddle_model = None
    if _paddle_processor is not None:
        del _paddle_processor
        _paddle_processor = None
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _paddleocr_vl_ocr(img_bytes: bytes) -> str:
    """Run OCR on a PNG image using PaddleOCR-VL (GPU, bfloat16)."""
    global _paddle_model, _paddle_processor
    try:
        import torch
        from PIL import Image

        if _paddle_model is None:
            preload_ocr_model()
        if _paddle_model is None:
            return ""

        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": OCR_PROMPT},
                ],
            }
        ]
        prompt = _paddle_processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _paddle_processor(
            text=[prompt], images=[image], return_tensors="pt"
        ).to("cuda")

        generated_ids = _paddle_model.generate(**inputs, max_new_tokens=2048)
        trimmed = [
            out[len(inp):]
            for inp, out in zip(inputs.input_ids, generated_ids)
        ]
        raw_text = _paddle_processor.batch_decode(trimmed, skip_special_tokens=True)[0]

        # Strip bounding-box location tags
        clean = _re.sub(r"<\|LOC_\d+\|>", "", raw_text)
        return clean.strip()
    except Exception as e:
        print(f"[OCR] PaddleOCR-VL inference failed: {e}", file=sys.stderr)
        return ""


def ocr_document(pdf_path: str, output_dir: str = None) -> dict:
    """
    High-level OCR function: extract text from a PDF file.
    Uses PyMuPDF for text-based PDFs, falls back to Ollama vision for scanned PDFs.

    Returns dict with keys: text, pages, method, markdown
    """
    import fitz  # PyMuPDF

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    page_texts = []
    method = "pymupdf"

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()

        if len(text) > 20:
            # Text-based PDF - PyMuPDF extraction works
            page_texts.append(text)
        else:
            # Scanned/image PDF - try PaddleOCR-VL first, then tesseract
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")

            ocr_text = _paddleocr_vl_ocr(img_bytes)
            if ocr_text and len(ocr_text) > 10:
                method = "paddleocr-vl"
                page_texts.append(ocr_text)
            else:
                # Fallback to tesseract
                method = "tesseract"
                import subprocess
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_bytes)
                    tmp_path = tmp.name
                try:
                    result = subprocess.run(
                        ["tesseract", tmp_path, "stdout", "-l", "eng"],
                        capture_output=True, text=True, timeout=60
                    )
                    page_texts.append(result.stdout.strip() or "[No text detected]")
                except Exception:
                    page_texts.append("[OCR unavailable]")
                finally:
                    os.unlink(tmp_path)

    doc.close()

    all_text = "\n\n".join(page_texts)
    markdown = build_markdown_document(page_texts, pdf_path, method)

    if output_dir:
        stem = Path(pdf_path).stem
        md_path = os.path.join(output_dir, f"{stem}.md")
        with open(md_path, "w") as f:
            f.write(markdown)

    return {
        "text": all_text,
        "pages": page_texts,
        "method": method,
        "page_count": len(page_texts),
        "markdown": markdown,
    }


def _ollama_vision_ocr(img_b64: str, model: str = GLM_OCR_MODEL) -> str:
    """Send an image to Ollama vision model for OCR."""
    try:
        payload = json.dumps({
            "model": model,
            "messages": [{
                "role": "user",
                "content": OCR_PROMPT,
                "images": [img_b64],
            }],
            "stream": False,
            "options": {"num_predict": 4096},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "")
    except Exception:
        return ""


def get_inference_backend():
    """Detect available inference backend, trying in order of preference."""
    # Try 1: Ollama with vision model
    if _ollama_is_alive() and _ollama_has_model(GLM_OCR_MODEL):
        return "ollama"

    # Try 2: transformers direct (reliable but slower)
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        return "transformers"
    except ImportError:
        pass

    # Fallback: Tesseract
    import shutil
    if shutil.which("tesseract"):
        return "tesseract"

    return None


def _ollama_is_alive() -> bool:
    """Check if Ollama server is reachable."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ollama_has_model(model: str) -> bool:
    """Check if the specified model is available in Ollama."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return any(m.get("name", "").startswith(model.split(":")[0]) for m in data.get("models", []))
    except Exception:
        return False


def infer_with_ollama(image_paths: list[str], model: str = GLM_OCR_MODEL) -> list[str]:
    """Run OCR inference using Ollama's vision API."""
    results = []
    for img_path in image_paths:
        try:
            with open(img_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = json.dumps({
                "model": model,
                "prompt": OCR_PROMPT,
                "images": [img_b64],
                "stream": False,
                "options": {"num_predict": 4096},
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{OLLAMA_BASE}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                text = data.get("response", "")
                results.append(text if text else "[No text extracted]")
        except Exception as e:
            print(f"  Ollama OCR error for {img_path}: {e}", file=sys.stderr)
            results.append(f"[ERROR: Ollama OCR failed for {os.path.basename(img_path)}: {e}]")

    return results


def infer_with_transformers(image_paths: list[str], model_name: str = "zai-org/GLM-OCR") -> list[str]:
    """Run GLM-OCR inference using transformers library."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
    from PIL import Image

    # Load model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32

    try:
        processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=dtype,
            device_map="auto" if device == "cuda" else None,
        )
    except Exception as e:
        print(f"Failed to load GLM-OCR model: {e}", file=sys.stderr)
        print("Falling back to Tesseract...", file=sys.stderr)
        return infer_with_tesseract(image_paths)

    results = []
    for img_path in image_paths:
        try:
            image = Image.open(img_path).convert("RGB")

            # GLM-OCR expects a specific prompt format
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": "Convert this document page to structured Markdown. "
                         "Preserve all text, tables, numbers, dates, and identifiers exactly. "
                         "Use proper Markdown formatting for headings, tables, and lists."}
                    ]
                }
            ]

            inputs = processor.apply_chat_template(
                messages, return_tensors="pt", add_generation_prompt=True
            )
            if isinstance(inputs, dict):
                inputs = {k: v.to(device) for k, v in inputs.items()}
            else:
                inputs = inputs.to(device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs if isinstance(inputs, dict) else {"input_ids": inputs},
                    max_new_tokens=4096,
                    do_sample=False,
                )

            if isinstance(inputs, dict):
                generated = outputs[0][inputs["input_ids"].shape[1]:]
            else:
                generated = outputs[0][inputs.shape[1]:]

            text = processor.decode(generated, skip_special_tokens=True)
            results.append(text)

        except Exception as e:
            print(f"Error processing {img_path}: {e}", file=sys.stderr)
            results.append(f"[ERROR: Failed to process {os.path.basename(img_path)}: {e}]")

    # Cleanup GPU memory
    if device == "cuda":
        del model
        import torch
        torch.cuda.empty_cache()

    return results


def infer_with_tesseract(image_paths: list[str]) -> list[str]:
    """Fallback: Use Tesseract OCR."""
    import subprocess
    results = []
    for img_path in image_paths:
        try:
            result = subprocess.run(
                ["tesseract", img_path, "stdout", "-l", "eng"],
                capture_output=True, text=True, timeout=60
            )
            text = result.stdout.strip()
            results.append(text if text else "[No text detected]")
        except Exception as e:
            results.append(f"[Tesseract error: {e}]")
    return results


def build_markdown_document(
    page_texts: list[str],
    source_file: str,
    extraction_method: str,
) -> str:
    """Combine page texts into a single Markdown document with frontmatter."""
    timestamp = datetime.now(timezone.utc).isoformat()
    source_basename = os.path.basename(source_file)

    frontmatter = f"""---
source_file: "{source_file}"
extraction_method: "{extraction_method}"
total_pages: {len(page_texts)}
timestamp: "{timestamp}"
agent_id: "glm-ocr-ingestor"
---

# Document: {source_basename}

"""
    body = ""
    for i, text in enumerate(page_texts):
        body += f"\n## Page {i + 1}\n\n{text}\n\n---\n"

    return frontmatter + body


def main():
    parser = argparse.ArgumentParser(description="GLM-OCR inference pipeline")
    parser.add_argument("--input-dir", required=True, help="Directory with preprocessed page images")
    parser.add_argument("--output-dir", required=True, help="Output directory for Markdown + provenance")
    parser.add_argument("--source-file", required=True, help="Original PDF file path (for provenance)")
    parser.add_argument("--model", default="zai-org/GLM-OCR", help="Model name or path")
    parser.add_argument("--backend", default="auto", choices=["auto", "ollama", "transformers", "tesseract"])
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Find preprocessed images
    image_patterns = ["*_preprocessed.png", "*.png", "*.jpg", "*.jpeg"]
    image_paths = []
    for pattern in image_patterns:
        found = sorted(glob.glob(os.path.join(args.input_dir, pattern)))
        if found:
            # Prefer preprocessed images
            if "_preprocessed" in pattern:
                image_paths = found
                break
            elif not image_paths:
                image_paths = found

    if not image_paths:
        print(f"ERROR: No images found in {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(image_paths)} page images...")

    # Select backend
    if args.backend == "auto":
        backend = get_inference_backend()
    else:
        backend = args.backend

    if backend is None:
        print("ERROR: No inference backend available. Install transformers or tesseract.", file=sys.stderr)
        sys.exit(1)

    print(f"Using backend: {backend}")

    # Run inference
    if backend == "ollama":
        page_texts = infer_with_ollama(image_paths, args.model if args.model != "zai-org/GLM-OCR" else GLM_OCR_MODEL)
    elif backend == "transformers":
        page_texts = infer_with_transformers(image_paths, args.model)
    elif backend == "tesseract":
        page_texts = infer_with_tesseract(image_paths)
    else:
        print(f"Backend '{backend}' not supported. Using tesseract.", file=sys.stderr)
        page_texts = infer_with_tesseract(image_paths)

    # Build output Markdown
    markdown = build_markdown_document(page_texts, args.source_file, f"glm-ocr-{backend}")

    # Write Markdown output
    source_stem = Path(args.source_file).stem
    md_path = os.path.join(args.output_dir, f"{source_stem}.md")
    with open(md_path, "w") as f:
        f.write(markdown)
    print(f"Markdown output: {md_path}")

    # Extract and validate fields
    from validator import extract_all_fields, compute_confidence
    from provenance import Provenance, ExtractedField, ExtractionResult

    all_text = "\n".join(page_texts)
    fields = extract_all_fields(all_text)

    extracted_fields = []
    for field_type, values in fields.items():
        for value in values:
            confidence = compute_confidence(field_type, value)
            prov = Provenance(
                source_file=args.source_file,
                extraction_method=f"glm-ocr-{backend}+regex",
                confidence=confidence,
                agent_id="glm-ocr-ingestor",
            )
            ef = ExtractedField(
                field_name=field_type,
                field_value=value,
                field_type=field_type,
                provenance=prov,
            )
            extracted_fields.append(ef)

    result = ExtractionResult(
        document_id=source_stem,
        source_file=args.source_file,
        extracted_fields=extracted_fields,
        raw_text=all_text,
        markdown=markdown,
    )

    # Write extraction result JSON
    json_path = os.path.join(args.output_dir, f"{source_stem}_extracted.json")
    with open(json_path, "w") as f:
        f.write(result.to_json())
    print(f"Extraction result: {json_path}")

    # Summary
    print(f"\nExtraction Summary:")
    for field_type, values in fields.items():
        print(f"  {field_type}: {len(values)} found")


if __name__ == "__main__":
    main()
