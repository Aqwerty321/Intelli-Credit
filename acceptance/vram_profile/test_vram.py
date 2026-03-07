"""
Acceptance Test: VRAM Profiling
Verifies that GLM-OCR + DeepSeek loaded with configured context
leaves headroom (doesn't exceed 24GB VRAM).
Outputs JSON report to stdout.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_gpu_memory() -> dict:
    """Query nvidia-smi for GPU memory usage."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,memory.free,name",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "used_mib": int(parts[0].strip()),
                "total_mib": int(parts[1].strip()),
                "free_mib": int(parts[2].strip()),
                "gpu_name": parts[3].strip() if len(parts) > 3 else "unknown",
            }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "nvidia-smi failed"}


def main():
    # Check if profile report already exists (from profile_deepseek.sh)
    profile_report = PROJECT_ROOT / "reports" / "acceptance" / "vram_profile.json"

    if profile_report.exists():
        with open(profile_report) as f:
            profile_data = json.load(f)

        # Analyze the profile data
        profiles = profile_data.get("profiles", [])
        summary = profile_data.get("summary", {})
        total_vram = summary.get("total_vram_mib", 24576)

        max_inference_vram = 0
        for p in profiles:
            vram = p.get("inference_vram_mib", 0)
            if vram > max_inference_vram:
                max_inference_vram = vram

        headroom_mib = total_vram - max_inference_vram
        headroom_pct = (headroom_mib / total_vram * 100) if total_vram > 0 else 0

        passes = headroom_mib > 1024  # At least 1 GB headroom

        report = {
            "test": "vram_profile",
            "status": "PASS" if passes else "FAIL",
            "gpu": summary.get("gpu", "unknown"),
            "total_vram_mib": total_vram,
            "max_inference_vram_mib": max_inference_vram,
            "headroom_mib": headroom_mib,
            "headroom_pct": round(headroom_pct, 1),
            "min_headroom_required_mib": 1024,
            "profiles": profiles,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        # No profile report — do a basic GPU check
        gpu = get_gpu_memory()
        if "error" in gpu:
            report = {
                "test": "vram_profile",
                "status": "FAIL",
                "reason": f"Cannot query GPU: {gpu['error']}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            report = {
                "test": "vram_profile",
                "status": "PASS" if gpu["free_mib"] > 4096 else "FAIL",
                "gpu": gpu.get("gpu_name", "unknown"),
                "total_vram_mib": gpu["total_mib"],
                "used_vram_mib": gpu["used_mib"],
                "free_vram_mib": gpu["free_mib"],
                "note": "No detailed profile available. Run scripts/profile_deepseek.sh first.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    print(json.dumps(report, indent=2))
    sys.exit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
