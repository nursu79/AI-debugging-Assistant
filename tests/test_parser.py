"""
test_parser.py — Tests for the Error Parser module

Tests cover:
- TypeError, IndexError, KeyError, AttributeError, ValueError, NameError
- File and line extraction
- Stack trace blocks
- Bare error messages (no file/line)
- Edge cases (empty input, unknown format)
"""

import pytest
from src.parser import parse_error, ErrorMetadata


# ---------------------------------------------------------------------------
# Sample tracebacks
# ---------------------------------------------------------------------------

TYPE_ERROR_TRACE = """\
Traceback (most recent call last):
  File "main.py", line 10, in <module>
    result = 5 + "hello"
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""

INDEX_ERROR_TRACE = """\
Traceback (most recent call last):
  File "app.py", line 23, in process
    item = my_list[10]
IndexError: list index out of range
"""

KEY_ERROR_TRACE = """\
Traceback (most recent call last):
  File "config.py", line 7, in load
    value = settings["missing_key"]
KeyError: 'missing_key'
"""

ATTRIBUTE_ERROR_TRACE = """\
Traceback (most recent call last):
  File "model.py", line 45, in predict
    output = self.model.predikt(data)
AttributeError: 'Sequential' object has no attribute 'predikt'
"""

VALUE_ERROR_TRACE = """\
Traceback (most recent call last):
  File "parser.py", line 18, in convert
    num = int("not_a_number")
ValueError: invalid literal for int() with base 10: 'not_a_number'
"""

NAME_ERROR_TRACE = """\
Traceback (most recent call last):
  File "script.py", line 3, in <module>
    print(undefined_variable)
NameError: name 'undefined_variable' is not defined
"""

MULTI_FRAME_TRACE = """\
Traceback (most recent call last):
  File "main.py", line 30, in main
    result = compute(data)
  File "utils.py", line 15, in compute
    return process(value)
  File "utils.py", line 8, in process
    return value / 0
ZeroDivisionError: division by zero
"""

BARE_ERROR = "TypeError: unsupported operand type(s) for +: 'int' and 'str'\nFile \"main.py\", line 10"


# ---------------------------------------------------------------------------
# Tests: error type extraction
# ---------------------------------------------------------------------------

class TestErrorTypeExtraction:
    def test_type_error(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        assert parsed.error_type == "TypeError"

    def test_index_error(self):
        parsed = parse_error(INDEX_ERROR_TRACE)
        assert parsed.error_type == "IndexError"

    def test_key_error(self):
        parsed = parse_error(KEY_ERROR_TRACE)
        assert parsed.error_type == "KeyError"

    def test_attribute_error(self):
        parsed = parse_error(ATTRIBUTE_ERROR_TRACE)
        assert parsed.error_type == "AttributeError"

    def test_value_error(self):
        parsed = parse_error(VALUE_ERROR_TRACE)
        assert parsed.error_type == "ValueError"

    def test_name_error(self):
        parsed = parse_error(NAME_ERROR_TRACE)
        assert parsed.error_type == "NameError"

    def test_zero_division_error(self):
        parsed = parse_error(MULTI_FRAME_TRACE)
        assert parsed.error_type == "ZeroDivisionError"


# ---------------------------------------------------------------------------
# Tests: message extraction
# ---------------------------------------------------------------------------

class TestMessageExtraction:
    def test_type_error_message(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        assert "unsupported operand" in parsed.message

    def test_key_error_message(self):
        parsed = parse_error(KEY_ERROR_TRACE)
        assert "missing_key" in parsed.message

    def test_attribute_error_message(self):
        parsed = parse_error(ATTRIBUTE_ERROR_TRACE)
        assert "predikt" in parsed.message

    def test_name_error_message(self):
        parsed = parse_error(NAME_ERROR_TRACE)
        assert "undefined_variable" in parsed.message


# ---------------------------------------------------------------------------
# Tests: file and line extraction
# ---------------------------------------------------------------------------

class TestFileAndLineExtraction:
    def test_type_error_file(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        assert parsed.file == "main.py"

    def test_type_error_line(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        assert parsed.line == 10

    def test_index_error_file_and_line(self):
        parsed = parse_error(INDEX_ERROR_TRACE)
        assert parsed.file == "app.py"
        assert parsed.line == 23

    def test_bare_error_line(self):
        """Bare error with File/line string (no Traceback header)"""
        parsed = parse_error(BARE_ERROR)
        assert parsed.line == 10
        assert parsed.error_type == "TypeError"

    def test_multi_frame_uses_innermost_frame(self):
        """Should use the innermost (last) file/line frame"""
        parsed = parse_error(MULTI_FRAME_TRACE)
        assert parsed.file == "utils.py"
        assert parsed.line == 8


# ---------------------------------------------------------------------------
# Tests: stack trace
# ---------------------------------------------------------------------------

class TestStackTrace:
    def test_stack_trace_present(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        assert "Traceback" in parsed.stack_trace

    def test_full_text_preserved(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        assert "result = 5" in parsed.full_text


# ---------------------------------------------------------------------------
# Tests: to_dict()
# ---------------------------------------------------------------------------

class TestToDictMethod:
    def test_to_dict_keys(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        d = parsed.to_dict()
        assert set(d.keys()) == {"error_type", "message", "file", "line", "stack_trace"}

    def test_to_dict_values(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        d = parsed.to_dict()
        assert d["error_type"] == "TypeError"
        assert d["line"] == 10
        assert d["file"] == "main.py"


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            parse_error("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            parse_error("   \n  ")

    def test_no_file_line_returns_none(self):
        """An error with no file reference should still parse the type"""
        err = "RuntimeError: something went wrong"
        parsed = parse_error(err)
        assert parsed.error_type == "RuntimeError"
        assert parsed.file is None
        assert parsed.line is None

    def test_returns_error_metadata_instance(self):
        parsed = parse_error(TYPE_ERROR_TRACE)
        assert isinstance(parsed, ErrorMetadata)
