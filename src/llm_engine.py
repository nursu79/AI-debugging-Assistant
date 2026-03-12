"""
llm_engine.py — LLM Integration via Ollama

Sends prompts to a locally running Ollama model and parses
the response into a validated DebugAnalysis object.

Supported models (via ollama pull):
  - deepseek-coder
  - codellama
  - starcoder2
"""

import json
import re
import time
import requests
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "deepseek-coder"
REQUEST_TIMEOUT = 120  # seconds
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"error_explanation", "root_cause", "suggested_fix", "corrected_code"}


@dataclass
class DebugAnalysis:
    """Structured result returned by the LLM engine."""
    error_explanation: str
    root_cause: str
    suggested_fix: str
    corrected_code: str
    raw_response: str = ""
    model: str = DEFAULT_MODEL
    parse_source: str = "json"   # "json" | "regex" | "fallback"

    def to_dict(self) -> dict:
        return {
            "error_explanation": self.error_explanation,
            "root_cause": self.root_cause,
            "suggested_fix": self.suggested_fix,
            "corrected_code": self.corrected_code,
        }

    def is_valid(self) -> bool:
        """Check that all fields are populated and non-trivial."""
        return all(
            isinstance(getattr(self, k), str) and len(getattr(self, k).strip()) > 0
            for k in ("error_explanation", "root_cause", "suggested_fix", "corrected_code")
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_error(
    prompt: str,
    model: str = DEFAULT_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> DebugAnalysis:
    """
    Send a debugging prompt to Ollama and return a structured DebugAnalysis.

    Args:
        prompt:   Fully constructed prompt from prompt_builder.
        model:    Ollama model name (deepseek-coder, codellama, etc.)
        base_url: Ollama server URL.

    Returns:
        DebugAnalysis with validated structured output.

    Raises:
        ConnectionError: If Ollama server is not reachable.
        RuntimeError:    If the LLM response cannot be parsed after retries.
    """
    _check_ollama_available(base_url)

    raw = _call_ollama(prompt, model, base_url)
    analysis = _parse_response(raw, model)
    return analysis


def list_available_models(base_url: str = OLLAMA_BASE_URL) -> list[str]:
    """Return names of models currently installed in Ollama."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except requests.exceptions.RequestException:
        return []


def is_ollama_running(base_url: str = OLLAMA_BASE_URL) -> bool:
    """Check if Ollama server is running."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _check_ollama_available(base_url: str) -> None:
    if not is_ollama_running(base_url):
        raise ConnectionError(
            f"Cannot reach Ollama at {base_url}. "
            "Make sure Ollama is running: `ollama serve`"
        )


def _call_ollama(prompt: str, model: str, base_url: str) -> str:
    """Call the Ollama /api/generate endpoint and return raw text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,   # Low temp → more deterministic / less hallucination
            "num_predict": 1024,
        },
    }

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = requests.post(
                f"{base_url}/api/generate",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.exceptions.Timeout:
            if attempt > MAX_RETRIES:
                raise RuntimeError(f"Ollama timed out after {REQUEST_TIMEOUT}s")
            time.sleep(1)
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Ollama request failed: {e}")


def _parse_response(raw: str, model: str) -> DebugAnalysis:
    """
    Try to parse the LLM response into a DebugAnalysis.
    Strategy: JSON → regex extraction → graceful fallback.
    """
    raw = raw.strip()

    # 1. Direct JSON parse
    result = _try_parse_json(raw)
    if result:
        return DebugAnalysis(**result, raw_response=raw, model=model, parse_source="json")

    # 2. Extract JSON block from markdown fences or mixed text
    result = _try_extract_json_block(raw)
    if result:
        return DebugAnalysis(**result, raw_response=raw, model=model, parse_source="json")

    # 3. Regex key extraction from unstructured text
    result = _try_regex_extraction(raw)
    if result:
        return DebugAnalysis(**result, raw_response=raw, model=model, parse_source="regex")

    # 4. Graceful fallback — put the entire response in explanation
    return DebugAnalysis(
        error_explanation=raw or "Unable to generate explanation.",
        root_cause="Could not determine root cause automatically.",
        suggested_fix="Please review the code manually.",
        corrected_code="# Could not generate corrected code.",
        raw_response=raw,
        model=model,
        parse_source="fallback",
    )


def _try_parse_json(text: str) -> Optional[dict]:
    """Attempt direct JSON parsing of the text."""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and REQUIRED_KEYS.issubset(data.keys()):
            return {k: str(data[k]) for k in REQUIRED_KEYS}
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _try_extract_json_block(text: str) -> Optional[dict]:
    """Find a JSON object inside markdown fences or surrounding text."""
    # Try to find {...} blocks
    patterns = [
        r"```(?:json)?\s*(\{.*?\})\s*```",  # markdown fenced
        r"(\{[^{}]*\"error_explanation\"[^{}]*\})",  # inline JSON with key
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            result = _try_parse_json(match.group(1))
            if result:
                return result
    return None


def _try_regex_extraction(text: str) -> Optional[dict]:
    """Last resort: extract values by matching key patterns in free text."""
    keys = {
        "error_explanation": r"(?:error.?explanation|explanation)[:\-]\s*(.+?)(?=\n\n|\Z|root.?cause)",
        "root_cause":        r"(?:root.?cause|cause)[:\-]\s*(.+?)(?=\n\n|\Z|suggested|fix)",
        "suggested_fix":     r"(?:suggested.?fix|fix|solution)[:\-]\s*(.+?)(?=\n\n|\Z|corrected)",
        "corrected_code":    r"(?:corrected.?code|corrected|fixed\s+code)[:\-]\s*(.+?)(?=\n\n|\Z)",
    }
    extracted = {}
    for key, pattern in keys.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        extracted[key] = match.group(1).strip() if match else ""

    if all(extracted.values()):
        return extracted
    return None
