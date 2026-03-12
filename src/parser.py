"""
parser.py — Runtime Error Parser

Extracts structured metadata from Python stack traces / error messages.
Handles: TypeError, IndexError, KeyError, AttributeError, ValueError,
         NameError, FileNotFoundError, ZeroDivisionError, and generic errors.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ErrorMetadata:
    """Structured representation of a parsed runtime error."""
    error_type: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    stack_trace: str = ""
    full_text: str = ""

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "stack_trace": self.stack_trace,
        }


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches the exception line:  TypeError: unsupported operand ...
_ERROR_TYPE_RE = re.compile(
    r'^(?P<error_type>[A-Za-z_]\w*(?:Error|Exception|Warning|Interrupt|Exit)'
    r'|KeyboardInterrupt|StopIteration|GeneratorExit|SystemExit)'
    r':\s*(?P<message>.+)$',
    re.MULTILINE,
)

# Matches CPython traceback frames:
#   File "main.py", line 10, in some_function
_FILE_LINE_RE = re.compile(
    r'File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+)',
    re.MULTILINE,
)

# Fallback: bare "line N" references without a file name
_LINE_ONLY_RE = re.compile(r'\bline\s+(?P<line>\d+)\b', re.IGNORECASE)


def parse_error(traceback_text: str) -> ErrorMetadata:
    """
    Parse a Python traceback / error string and return an ErrorMetadata object.

    Args:
        traceback_text: Raw traceback string from sys.exc_info() or copied output.

    Returns:
        ErrorMetadata with extracted fields.

    Raises:
        ValueError: If the input is empty or no error type can be found.
    """
    if not traceback_text or not traceback_text.strip():
        raise ValueError("traceback_text must not be empty")

    text = traceback_text.strip()

    # --- Extract error type + message ---
    error_type, message = _extract_error_type_and_message(text)

    # --- Extract file + line ---
    file_path, line_number = _extract_file_and_line(text)

    # --- Extract stack trace block (everything before the final error line) ---
    stack_trace = _extract_stack_trace(text)

    return ErrorMetadata(
        error_type=error_type,
        message=message,
        file=file_path,
        line=line_number,
        stack_trace=stack_trace,
        full_text=text,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_error_type_and_message(text: str):
    """Return (error_type, message) from the traceback text."""
    match = _ERROR_TYPE_RE.search(text)
    if match:
        return match.group("error_type"), match.group("message").strip()

    # Fallback: last non-empty line might be the error (e.g. bare SyntaxError)
    last_line = next(
        (l.strip() for l in reversed(text.splitlines()) if l.strip()), ""
    )
    if ":" in last_line:
        parts = last_line.split(":", 1)
        return parts[0].strip(), parts[1].strip()

    return "UnknownError", last_line or "Unknown error occurred"


def _extract_file_and_line(text: str):
    """Return (file_path, line_number) from the *last* File/line reference."""
    matches = _FILE_LINE_RE.findall(text)
    if matches:
        # Use the innermost (last) frame as it is closest to the error.
        file_path, line_str = matches[-1]
        return file_path, int(line_str)

    # Fallback: search for bare "line N"
    match = _LINE_ONLY_RE.search(text)
    if match:
        return None, int(match.group("line"))

    return None, None


def _extract_stack_trace(text: str) -> str:
    """Extract the Traceback block if present, else return the whole text."""
    if "Traceback (most recent call last):" in text:
        return text
    # If there's no Traceback header, return just the last few lines as context
    lines = text.splitlines()
    return "\n".join(lines[-10:]) if len(lines) > 10 else text
