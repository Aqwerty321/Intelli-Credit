"""
Cognitive inference service for Intelli-Credit.
Uses Ollama (primary) with DeepSeek-R1-8B-Llama-Distill-Abliterated-Q8_0
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

# Ollama model names
DEEPSEEK_MODEL = "sjo/deepseek-r1-8b-llama-distill-abliterated-q8_0:latest"
GLM_OCR_MODEL = "glm-ocr:bf16"
# Lightweight model for fast orchestration tasks (routing, judging, claim building)
LIGHT_MODEL = "llama3.2:3b"

# Ollama API base (auto-detect: env var > Windows host from WSL2 > localhost)
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://172.23.112.1:11434")


@dataclass
class CognitiveResponse:
    """Response from the cognitive inference engine."""
    raw_text: str
    thinking: str = ""
    answer: str = ""
    model: str = DEEPSEEK_MODEL
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
        answer = raw_text

    return thinking, answer


class CognitiveEngine:
    """Interface to Ollama for structured reasoning."""

    def __init__(self, base_url: str = OLLAMA_BASE,
                 model: str = DEEPSEEK_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def is_alive(self) -> bool:
        """Check if Ollama is running."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def list_models(self) -> list[str]:
        """List available Ollama models."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return [m["name"] for m in data.get("models", [])]
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return []

    def generate(self, prompt: str, system: str = "",
                 max_tokens: int = 4096,
                 temperature: float = 0.1,
                 model: str = None) -> CognitiveResponse:
        """Send a generate request to Ollama."""
        t0 = time.time()
        use_model = model or self.model

        payload = json.dumps({
            "model": use_model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, OSError) as e:
            return CognitiveResponse(
                raw_text=f"[ERROR: Ollama unavailable: {e}]",
                model=use_model,
            )

        raw_text = data.get("response", "")
        thinking, answer = parse_thinking(raw_text)
        latency = (time.time() - t0) * 1000

        return CognitiveResponse(
            raw_text=raw_text,
            thinking=thinking,
            answer=answer,
            model=use_model,
            tokens_used=data.get("eval_count", 0),
            latency_ms=latency,
        )

    def chat(self, messages: list[dict], max_tokens: int = 4096,
             temperature: float = 0.1,
             model: str = None) -> CognitiveResponse:
        """Send a chat request to Ollama."""
        t0 = time.time()
        use_model = model or self.model

        payload = json.dumps({
            "model": use_model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, OSError) as e:
            return CognitiveResponse(
                raw_text=f"[ERROR: Ollama unavailable: {e}]",
                model=use_model,
            )

        raw_text = data.get("message", {}).get("content", "")
        thinking, answer = parse_thinking(raw_text)
        latency = (time.time() - t0) * 1000

        return CognitiveResponse(
            raw_text=raw_text,
            thinking=thinking,
            answer=answer,
            model=use_model,
            tokens_used=data.get("eval_count", 0),
            latency_ms=latency,
        )

    def analyze_document(self, document_text: str, context: str = "") -> CognitiveResponse:
        """Analyze a document for credit decisioning."""
        system = """You are a senior credit analyst at an Indian MSME lending institution.
Analyze the provided document and extract:
1. Key financial indicators (revenue, profit, debt ratios)
2. Risk signals (DPD, delinquencies, litigation)
3. GST compliance status (ITC mismatches, circular trading indicators)
4. Promoter background concerns
5. Overall credit quality assessment

Always cite specific numbers and references from the document."""

        if context:
            system += f"\n\nAdditional context:\n{context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Analyze this document for credit appraisal:\n\n{document_text[:12000]}"},
        ]
        return self.chat(messages)

    def assess_risk(self, facts: dict) -> CognitiveResponse:
        """Get a structured risk assessment from the LLM."""
        facts_str = json.dumps(facts, indent=2)

        system = """You are a risk assessment engine for Indian MSME lending.
Given the extracted facts, provide:
1. Risk classification (LOW / MEDIUM / HIGH / CRITICAL)
2. Key risk factors with severity
3. Recommended loan terms (approve/reject/conditional, risk premium in bps)
4. Missing information that would improve the assessment

Output a JSON object with your assessment."""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Facts extracted from the borrower's documents:\n\n{facts_str}"},
        ]
        return self.chat(messages)

    def extract_fields(self, document_text: str) -> CognitiveResponse:
        """Extract structured fields from document text using LLM."""
        system = """You are a document extraction engine for Indian corporate documents.
Extract ALL of the following fields from the text. Return a JSON object:
{
  "gstin": ["list of GSTINs found"],
  "pan": ["list of PANs found"],
  "company_name": "company name",
  "cin": "Company Identification Number if found",
  "amounts": [{"label": "description", "value": numeric_value}],
  "dates": [{"label": "description", "value": "DD/MM/YYYY"}],
  "key_financials": {"revenue": null, "profit": null, "debt": null},
  "risk_indicators": {"dpd": null, "cmr_rank": null, "dishonoured_cheques": null}
}
Only include fields you find. Use null for missing fields."""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Extract structured fields from this document:\n\n{document_text[:8000]}"},
        ]
        return self.chat(messages)


# Singleton engine
_engine: Optional[CognitiveEngine] = None


def get_engine(base_url: str = OLLAMA_BASE,
               model: str = DEEPSEEK_MODEL) -> CognitiveEngine:
    """Get the singleton CognitiveEngine instance."""
    global _engine
    if _engine is None:
        _engine = CognitiveEngine(base_url, model)
    return _engine
