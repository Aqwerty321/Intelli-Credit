"""
Cognitive inference service for Intelli-Credit.
Wraps llama.cpp server (DeepSeek-R1-Distill-Llama-8B Q4_K_M)
for structured reasoning with <think>...</think> chain-of-thought.
"""
import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models"
DEFAULT_MODEL = MODEL_DIR / "DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf"
LLAMA_SERVER = PROJECT_ROOT / "llama.cpp" / "build" / "bin" / "llama-server"


@dataclass
class CognitiveResponse:
    """Response from the cognitive inference engine."""
    raw_text: str
    thinking: str = ""
    answer: str = ""
    model: str = "deepseek-r1-distill-llama-8b-q4"
    tokens_used: int = 0
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "thinking": self.thinking,
            "answer": self.answer,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
        }


def parse_thinking(raw_text: str) -> tuple[str, str]:
    """Parse <think>...</think> tags from model output."""
    thinking = ""
    answer = raw_text

    if "<think>" in raw_text:
        parts = raw_text.split("<think>", 1)
        if "</think>" in parts[1]:
            think_parts = parts[1].split("</think>", 1)
            thinking = think_parts[0].strip()
            answer = think_parts[1].strip()
        else:
            thinking = parts[1].strip()
            answer = ""
    elif "think>" in raw_text.lower():
        # Handle edge cases with malformed tags
        answer = raw_text

    return thinking, answer


class CognitiveEngine:
    """Interface to the llama.cpp server for structured reasoning."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip("/")
        self._server_process = None

    def is_alive(self) -> bool:
        """Check if the llama.cpp server is running."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return data.get("status") == "ok"
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return False

    def start_server(self, model_path: str = None, ctx_size: int = 8192,
                     gpu_layers: int = 33, port: int = 8080) -> bool:
        """Start the llama.cpp server if not already running."""
        if self.is_alive():
            print("  llama.cpp server already running")
            return True

        model_path = model_path or str(DEFAULT_MODEL)
        server_bin = str(LLAMA_SERVER)

        if not os.path.exists(server_bin):
            # Try alternative locations
            alt_paths = [
                PROJECT_ROOT / "llama.cpp" / "llama-server",
                PROJECT_ROOT / "llama.cpp" / "server",
            ]
            for alt in alt_paths:
                if alt.exists():
                    server_bin = str(alt)
                    break
            else:
                print("  ERROR: llama-server binary not found")
                return False

        if not os.path.exists(model_path):
            print(f"  ERROR: Model not found: {model_path}")
            return False

        cmd = [
            server_bin,
            "-m", model_path,
            "-c", str(ctx_size),
            "-ngl", str(gpu_layers),
            "--port", str(port),
            "--host", "127.0.0.1",
        ]

        print(f"  Starting llama.cpp server: {' '.join(cmd[:4])}...")
        self._server_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Wait for server to be ready
        for i in range(30):
            time.sleep(2)
            if self.is_alive():
                print(f"  Server ready (took {(i+1)*2}s)")
                return True

        print("  Server failed to start within 60s")
        return False

    def stop_server(self):
        """Stop the llama.cpp server."""
        if self._server_process:
            self._server_process.terminate()
            self._server_process.wait(timeout=10)
            self._server_process = None

    def complete(self, prompt: str, max_tokens: int = 4096,
                 temperature: float = 0.1) -> CognitiveResponse:
        """Send a completion request to the server."""
        t0 = time.time()

        payload = json.dumps({
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": ["<|endoftext|>", "<|end|>"],
            "stream": False,
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/completion",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, OSError) as e:
            return CognitiveResponse(
                raw_text=f"[ERROR: Server unavailable: {e}]",
            )

        raw_text = data.get("content", "")
        thinking, answer = parse_thinking(raw_text)
        latency = (time.time() - t0) * 1000

        return CognitiveResponse(
            raw_text=raw_text,
            thinking=thinking,
            answer=answer,
            tokens_used=data.get("tokens_predicted", 0),
            latency_ms=latency,
        )

    def analyze_document(self, document_text: str, context: str = "") -> CognitiveResponse:
        """Analyze a document for credit decisioning."""
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a senior credit analyst at an Indian MSME lending institution.
Analyze the provided document and extract:
1. Key financial indicators (revenue, profit, debt ratios)
2. Risk signals (DPD, delinquencies, litigation)
3. GST compliance status (ITC mismatches, circular trading indicators)
4. Promoter background concerns
5. Overall credit quality assessment

Use <think>...</think> tags to show your reasoning before providing conclusions.
Always cite specific numbers and page references.
{context}
<|eot_id|><|start_header_id|>user<|end_header_id|>
Analyze this document for credit appraisal:

{document_text[:12000]}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
        return self.complete(prompt)

    def assess_risk(self, facts: dict) -> CognitiveResponse:
        """Get a structured risk assessment from the LLM."""
        facts_str = json.dumps(facts, indent=2)
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a risk assessment engine for Indian MSME lending.
Given the extracted facts, provide:
1. Risk classification (LOW / MEDIUM / HIGH / CRITICAL)
2. Key risk factors with severity
3. Recommended loan terms (approve/reject/conditional, risk premium)
4. Missing information that would improve the assessment

Use <think>...</think> for your reasoning chain.
Output a JSON object after your thinking.
<|eot_id|><|start_header_id|>user<|end_header_id|>
Facts extracted from the borrower's documents:

{facts_str}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
        return self.complete(prompt)


# Singleton engine
_engine: Optional[CognitiveEngine] = None


def get_engine(base_url: str = "http://127.0.0.1:8080") -> CognitiveEngine:
    """Get the singleton CognitiveEngine instance."""
    global _engine
    if _engine is None:
        _engine = CognitiveEngine(base_url)
    return _engine
