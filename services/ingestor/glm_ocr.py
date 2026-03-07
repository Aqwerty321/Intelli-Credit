"""
GLM-OCR inference service for Intelli-Credit.
Converts preprocessed document images to structured Markdown with provenance.

Usage:
  python glm_ocr.py --input-dir <dir_with_images> --output-dir <output> --source-file <original.pdf>

Backend priority: vLLM -> SGLang -> transformers direct -> Tesseract fallback
"""
import argparse
import json
import os
import sys
import glob
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_inference_backend():
    """Detect available inference backend, trying in order of preference."""
    # Try 1: vLLM (fastest, batched)
    try:
        from vllm import LLM
        return "vllm"
    except ImportError:
        pass

    # Try 2: SGLang
    try:
        import sglang
        return "sglang"
    except ImportError:
        pass

    # Try 3: transformers direct (reliable but slower)
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
    parser.add_argument("--backend", default="auto", choices=["auto", "vllm", "sglang", "transformers", "tesseract"])
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
    if backend == "transformers":
        page_texts = infer_with_transformers(image_paths, args.model)
    elif backend == "tesseract":
        page_texts = infer_with_tesseract(image_paths)
    else:
        # vLLM and SGLang would use their server APIs
        # For now, fall back to transformers
        print(f"Backend '{backend}' integration pending. Using transformers.", file=sys.stderr)
        page_texts = infer_with_transformers(image_paths, args.model)

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
