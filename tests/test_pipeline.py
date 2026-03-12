"""
test_pipeline.py — End-to-end Pipeline Tests

Mocks the LLM call to verify the full flow:
  parse → retrieve → build → mock_llm → return
"""

import pytest
from unittest.mock import patch
from src.debug_assistant import run_debug_pipeline

# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

ERROR_TRACE = """\
Traceback (most recent call last):
  File "calculator.py", line 4, in divide
    return x / y
ZeroDivisionError: division by zero
"""

CODE = """\
def divide(x, y):
    # This should fail if y is 0
    return x / y

result = divide(10, 0)
"""

MOCK_ANALYSIS = {
    "error_explanation": "A ZeroDivisionError occurs when trying to divide by zero.",
    "root_cause": "The variable 'y' is passed as 0 to the divide function.",
    "suggested_fix": "Check if y is 0 before performing division.",
    "corrected_code": "return x / y if y != 0 else 0"
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFullPipeline:
    @patch("src.debug_assistant.is_ollama_running", return_value=True)
    @patch("src.debug_assistant.analyze_error")
    def test_run_debug_pipeline_success(self, mock_analyze, mock_running):
        # Setup mock
        from src.llm_engine import DebugAnalysis
        mock_analyze.return_value = DebugAnalysis(
            **MOCK_ANALYSIS,
            raw_response="...",
            model="deepseek-coder",
            parse_source="json"
        )

        result = run_debug_pipeline(
            error_message=ERROR_TRACE,
            code=CODE,
            model="deepseek-coder"
        )

        # Verify steps were executed correctly
        assert result["error_explanation"] == MOCK_ANALYSIS["error_explanation"]
        assert result["root_cause"] == MOCK_ANALYSIS["root_cause"]
        assert result["_meta"]["error_type"] == "ZeroDivisionError"
        assert result["_meta"]["line"] == 4  # File "calculator.py", line 4

    @patch("src.debug_assistant.is_ollama_running", return_value=True)
    @patch("src.debug_assistant.analyze_error")
    def test_pipeline_with_file_path(self, mock_analyze, mock_running, tmp_path):
        # Create temp file
        f = tmp_path / "calc.py"
        f.write_text(CODE)

        from src.llm_engine import DebugAnalysis
        mock_analyze.return_value = DebugAnalysis(
            **MOCK_ANALYSIS,
            raw_response="...",
            model="deepseek-coder",
            parse_source="json"
        )

        # Use file_path instead of inline code
        result = run_debug_pipeline(
            error_message=ERROR_TRACE.replace("calculator.py", str(f)),
            file_path=str(f)
        )

        assert result["_meta"]["file"] == str(f)
        assert result["suggested_fix"] == MOCK_ANALYSIS["suggested_fix"]

    def test_pipeline_missing_source_raises(self):
        with pytest.raises(ValueError, match=r"Provide either 'code' \(string\) or 'file_path'"):
            run_debug_pipeline(error_message=ERROR_TRACE)

    @patch("src.debug_assistant.is_ollama_running", return_value=False)
    def test_pipeline_no_ollama_raises(self, mock_running):
        with pytest.raises(ConnectionError, match="Cannot reach Ollama"):
            run_debug_pipeline(error_message=ERROR_TRACE, code=CODE)
