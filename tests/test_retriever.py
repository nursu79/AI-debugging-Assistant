"""
test_retriever.py — Tests for the Code Context Retriever

Tests cover:
- Retrieval from file path
- Retrieval from raw code string
- Window boundaries (start/end of file)
- Error line annotation marker
- contains() helper
- Edge cases: no line number, missing file, empty code
"""

import os
import tempfile
import pytest
from src.retriever import get_context, CodeContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CODE = """\
def add(a, b):
    return a + b

def greet(name):
    message = "Hello, " + name
    print(message)
    return message

def divide(x, y):
    return x / y

def main():
    result = add(5, "hello")
    print(result)

if __name__ == "__main__":
    main()
"""


@pytest.fixture
def sample_file(tmp_path):
    """Write sample code to a temp file and return its path."""
    f = tmp_path / "sample_code.py"
    f.write_text(SAMPLE_CODE, encoding="utf-8")
    return str(f)


# ---------------------------------------------------------------------------
# Tests: retrieval from code string
# ---------------------------------------------------------------------------

class TestCodeStringRetrieval:
    def test_returns_code_context(self):
        ctx = get_context(code_string=SAMPLE_CODE, line_number=5)
        assert isinstance(ctx, CodeContext)

    def test_contains_error_line(self):
        """Line 5 is the problematic line (string + string concatenation)"""
        ctx = get_context(code_string=SAMPLE_CODE, line_number=5)
        assert ctx.contains("Hello")

    def test_window_size_default(self):
        """Default window of 5: lines 1-10 around line 5"""
        ctx = get_context(code_string=SAMPLE_CODE, line_number=5)
        assert ctx.start_line <= 5
        assert ctx.end_line >= 5
        total_lines = ctx.end_line - ctx.start_line + 1
        assert total_lines <= 11  # window_size*2 + 1

    def test_custom_window_size(self):
        ctx = get_context(code_string=SAMPLE_CODE, line_number=10, window_size=2)
        total_lines = len(ctx.lines)
        assert total_lines <= 5  # 2 before + error + 2 after

    def test_start_boundary_clamped(self):
        """Line 1 — should not go below line 1"""
        ctx = get_context(code_string=SAMPLE_CODE, line_number=1)
        assert ctx.start_line == 1

    def test_end_boundary_clamped(self):
        """Last line — should not go past end of file"""
        total = len(SAMPLE_CODE.splitlines())
        ctx = get_context(code_string=SAMPLE_CODE, line_number=total)
        assert ctx.end_line == total


# ---------------------------------------------------------------------------
# Tests: retrieval from file path
# ---------------------------------------------------------------------------

class TestFilePathRetrieval:
    def test_reads_from_file(self, sample_file):
        ctx = get_context(file_path=sample_file, line_number=13)
        assert ctx.file_path == sample_file

    def test_contains_expected_line(self, sample_file):
        """Line 13 has: result = add(5, "hello")"""
        ctx = get_context(file_path=sample_file, line_number=13)
        assert ctx.contains('add(5, "hello")')

    def test_error_line_recorded(self, sample_file):
        ctx = get_context(file_path=sample_file, line_number=13)
        assert ctx.error_line == 13

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            get_context(file_path="/nonexistent/path/fake.py", line_number=1)


# ---------------------------------------------------------------------------
# Tests: snippet formatting
# ---------------------------------------------------------------------------

class TestSnippetFormatting:
    def test_snippet_contains_line_numbers(self):
        ctx = get_context(code_string=SAMPLE_CODE, line_number=5)
        assert "5" in ctx.snippet

    def test_snippet_marks_error_line(self):
        ctx = get_context(code_string=SAMPLE_CODE, line_number=5)
        lines = ctx.snippet.splitlines()
        error_lines = [l for l in lines if l.strip().startswith(">>>")]
        assert len(error_lines) == 1

    def test_raw_code_no_markers(self):
        ctx = get_context(code_string=SAMPLE_CODE, line_number=5)
        assert ">>>" not in ctx.raw_code
        assert "|" not in ctx.raw_code

    def test_to_dict_has_expected_keys(self):
        ctx = get_context(code_string=SAMPLE_CODE, line_number=5)
        d = ctx.to_dict()
        assert set(d.keys()) == {"file_path", "error_line", "start_line", "end_line", "snippet"}


# ---------------------------------------------------------------------------
# Tests: no line number provided
# ---------------------------------------------------------------------------

class TestNoLineNumber:
    def test_no_line_number_returns_context(self):
        ctx = get_context(code_string=SAMPLE_CODE)
        assert ctx.error_line is None
        assert len(ctx.lines) > 0

    def test_no_line_number_returns_whole_small_file(self):
        short_code = "x = 1\ny = 2\n"
        ctx = get_context(code_string=short_code)
        assert ctx.start_line == 1
        assert ctx.end_line == 2


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_source_raises(self):
        with pytest.raises(ValueError, match="Either file_path or code_string"):
            get_context(line_number=5)

    def test_empty_code_string(self):
        ctx = get_context(code_string="")
        assert ctx.lines == []

    def test_out_of_range_line_falls_back(self):
        """Line number beyond file length — should still not crash"""
        ctx = get_context(code_string=SAMPLE_CODE, line_number=9999)
        # Falls back to returning full file (up to 50 lines)
        assert len(ctx.lines) > 0
