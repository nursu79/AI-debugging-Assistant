"""
test_llm_engine.py — Tests for the LLM Engine (Ollama integration)

Uses unittest.mock to avoid requiring a live Ollama server.
Tests cover:
  - Successful JSON response parsing
  - Markdown fence JSON extraction
  - Regex fallback extraction
  - Graceful fallback on unparseable response
  - Connection error handling
  - DebugAnalysis.is_valid() and to_dict()
  - Ollama availability check
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import requests

from src.llm_engine import (
    analyze_error,
    DebugAnalysis,
    is_ollama_running,
    list_available_models,
    _parse_response,
    _try_parse_json,
    _try_extract_json_block,
    _try_regex_extraction,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_JSON_RESPONSE = json.dumps({
    "error_explanation": "This TypeError occurs when adding int and str.",
    "root_cause": "Variable 'y' is a string but is being added to an int 'x'.",
    "suggested_fix": "Convert 'y' to int before adding: int(y).",
    "corrected_code": "result = x + int(y)",
})

MARKDOWN_FENCE_RESPONSE = f"""
Sure! Here is the analysis:

```json
{VALID_JSON_RESPONSE}
```
"""

REGEX_EXTRACTION_RESPONSE = """
Error Explanation: This TypeError occurs when adding int and str.

Root Cause: Variable 'y' is a string.

Suggested Fix: Convert y to int.

Corrected Code: result = x + int(y)
"""

GIBBERISH_RESPONSE = "I cannot help with that."

SAMPLE_PROMPT = "Analyze this error: TypeError"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def mock_ollama_response(text: str):
    """Create a mock requests.post response object."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": text}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def mock_tags_response(models=None):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": models or [{"name": "deepseek-coder"}]}
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: _try_parse_json
# ---------------------------------------------------------------------------

class TestTryParseJson:
    def test_valid_json(self):
        result = _try_parse_json(VALID_JSON_RESPONSE)
        assert result is not None
        assert result["error_explanation"] == "This TypeError occurs when adding int and str."

    def test_missing_key(self):
        data = {"error_explanation": "x", "root_cause": "y"}
        result = _try_parse_json(json.dumps(data))
        assert result is None  # missing suggested_fix and corrected_code

    def test_invalid_json(self):
        result = _try_parse_json("this is not json")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _try_extract_json_block
# ---------------------------------------------------------------------------

class TestExtractJsonBlock:
    def test_extracts_from_markdown_fence(self):
        result = _try_extract_json_block(MARKDOWN_FENCE_RESPONSE)
        assert result is not None
        assert "error_explanation" in result

    def test_returns_none_for_gibberish(self):
        result = _try_extract_json_block(GIBBERISH_RESPONSE)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _try_regex_extraction
# ---------------------------------------------------------------------------

class TestRegexExtraction:
    def test_extracts_from_labelled_text(self):
        result = _try_regex_extraction(REGEX_EXTRACTION_RESPONSE)
        assert result is not None
        assert "TypeError" in result["error_explanation"]

    def test_returns_none_for_gibberish(self):
        result = _try_regex_extraction(GIBBERISH_RESPONSE)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_parses_clean_json(self):
        analysis = _parse_response(VALID_JSON_RESPONSE, "deepseek-coder")
        assert analysis.parse_source == "json"
        assert analysis.error_explanation != ""

    def test_parses_markdown_fence(self):
        analysis = _parse_response(MARKDOWN_FENCE_RESPONSE, "deepseek-coder")
        assert analysis.parse_source == "json"

    def test_graceful_fallback(self):
        analysis = _parse_response(GIBBERISH_RESPONSE, "deepseek-coder")
        assert analysis.parse_source == "fallback"
        assert isinstance(analysis.error_explanation, str)

    def test_raw_response_preserved(self):
        analysis = _parse_response(VALID_JSON_RESPONSE, "deepseek-coder")
        assert analysis.raw_response == VALID_JSON_RESPONSE


# ---------------------------------------------------------------------------
# Tests: DebugAnalysis
# ---------------------------------------------------------------------------

class TestDebugAnalysis:
    def test_is_valid_all_fields(self):
        a = DebugAnalysis(
            error_explanation="Explanation",
            root_cause="Root cause",
            suggested_fix="Fix",
            corrected_code="x = 1",
        )
        assert a.is_valid() is True

    def test_is_valid_empty_field(self):
        a = DebugAnalysis(
            error_explanation="",
            root_cause="Root cause",
            suggested_fix="Fix",
            corrected_code="x = 1",
        )
        assert a.is_valid() is False

    def test_to_dict_keys(self):
        a = DebugAnalysis(
            error_explanation="E", root_cause="R",
            suggested_fix="S", corrected_code="C"
        )
        d = a.to_dict()
        assert set(d.keys()) == {"error_explanation", "root_cause", "suggested_fix", "corrected_code"}


# ---------------------------------------------------------------------------
# Tests: analyze_error (with mocked Ollama)
# ---------------------------------------------------------------------------

class TestAnalyzeError:
    @patch("src.llm_engine.is_ollama_running", return_value=True)
    @patch("src.llm_engine.requests.post")
    def test_successful_analysis(self, mock_post, mock_running):
        mock_post.return_value = mock_ollama_response(VALID_JSON_RESPONSE)
        result = analyze_error(SAMPLE_PROMPT)
        assert isinstance(result, DebugAnalysis)
        assert result.is_valid()

    @patch("src.llm_engine.is_ollama_running", return_value=True)
    @patch("src.llm_engine.requests.post")
    def test_markdown_fence_response(self, mock_post, mock_running):
        mock_post.return_value = mock_ollama_response(MARKDOWN_FENCE_RESPONSE)
        result = analyze_error(SAMPLE_PROMPT)
        assert result.parse_source == "json"
        assert result.is_valid()

    @patch("src.llm_engine.is_ollama_running", return_value=True)
    @patch("src.llm_engine.requests.post")
    def test_fallback_on_gibberish(self, mock_post, mock_running):
        mock_post.return_value = mock_ollama_response(GIBBERISH_RESPONSE)
        result = analyze_error(SAMPLE_PROMPT)
        assert result.parse_source == "fallback"
        assert isinstance(result, DebugAnalysis)

    @patch("src.llm_engine.is_ollama_running", return_value=False)
    def test_raises_on_ollama_not_running(self, mock_running):
        with pytest.raises(ConnectionError, match="Cannot reach Ollama"):
            analyze_error(SAMPLE_PROMPT)

    @patch("src.llm_engine.is_ollama_running", return_value=True)
    @patch("src.llm_engine.requests.post")
    def test_model_name_recorded(self, mock_post, mock_running):
        mock_post.return_value = mock_ollama_response(VALID_JSON_RESPONSE)
        result = analyze_error(SAMPLE_PROMPT, model="codellama")
        assert result.model == "codellama"


# ---------------------------------------------------------------------------
# Tests: utility functions
# ---------------------------------------------------------------------------

class TestUtilityFunctions:
    @patch("src.llm_engine.requests.get")
    def test_is_ollama_running_true(self, mock_get):
        mock_get.return_value.status_code = 200
        assert is_ollama_running() is True

    @patch("src.llm_engine.requests.get", side_effect=requests.exceptions.ConnectionError)
    def test_is_ollama_running_false(self, mock_get):
        assert is_ollama_running() is False

    @patch("src.llm_engine.requests.get")
    def test_list_models(self, mock_get):
        mock_get.return_value = mock_tags_response([{"name": "deepseek-coder"}, {"name": "codellama"}])
        models = list_available_models()
        assert "deepseek-coder" in models
        assert "codellama" in models
