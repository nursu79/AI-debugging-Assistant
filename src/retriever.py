"""
retriever.py — Code Context Retriever

Retrieves relevant lines of code surrounding an error location.
Supports reading from:
  - File paths on disk
  - Raw code strings passed directly (for API usage)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CodeContext:
    """Holds a code window around the error line."""
    file_path: Optional[str]
    error_line: Optional[int]
    start_line: int
    end_line: int
    lines: list[str]
    window_size: int

    @property
    def snippet(self) -> str:
        """Return annotated code snippet with line numbers."""
        parts = []
        for i, line in enumerate(self.lines):
            lineno = self.start_line + i
            marker = ">>>" if lineno == self.error_line else "   "
            parts.append(f"{marker} {lineno:4d} | {line.rstrip()}")
        return "\n".join(parts)

    @property
    def raw_code(self) -> str:
        """Return code without annotations (for prompt injection)."""
        return "\n".join(line.rstrip() for line in self.lines)

    def contains(self, text: str) -> bool:
        """Check if any retrieved line contains the given text."""
        return any(text in line for line in self.lines)

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "error_line": self.error_line,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "snippet": self.snippet,
        }


def get_context(
    file_path: Optional[str] = None,
    line_number: Optional[int] = None,
    code_string: Optional[str] = None,
    window_size: int = 5,
) -> CodeContext:
    """
    Retrieve code lines surrounding the error location.

    Either `file_path` or `code_string` must be provided.

    Args:
        file_path:   Path to the Python source file on disk.
        line_number: The 1-indexed line where the error occurred.
        code_string: Raw code content (used when no file path is available).
        window_size: Number of lines to include before and after error line.

    Returns:
        CodeContext containing the retrieved lines and metadata.

    Raises:
        ValueError: If neither file_path nor code_string is provided.
        FileNotFoundError: If file_path is given but the file doesn't exist.
    """
    if file_path is None and code_string is None:
        raise ValueError("Either file_path or code_string must be provided.")

    all_lines = _load_lines(file_path, code_string)
    total = len(all_lines)

    # Determine window boundaries (1-indexed → 0-indexed internally)
    if line_number is not None and 1 <= line_number <= total:
        start = max(0, line_number - 1 - window_size)
        end = min(total, line_number + window_size)  # exclusive
    else:
        # No valid line number — return the entire file (up to 50 lines)
        start = 0
        end = min(total, 50)
        line_number = None

    selected = all_lines[start:end]

    return CodeContext(
        file_path=file_path,
        error_line=line_number,
        start_line=start + 1,      # back to 1-indexed
        end_line=start + len(selected),
        lines=selected,
        window_size=window_size,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_lines(file_path: Optional[str], code_string: Optional[str]) -> list[str]:
    """Load source lines from file or string."""
    if code_string is not None:
        return code_string.splitlines(keepends=True)
    # file_path is guaranteed non-None here
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            return fh.readlines()
    except FileNotFoundError:
        raise FileNotFoundError(f"Source file not found: {file_path}")
    except PermissionError:
        raise PermissionError(f"Cannot read file (permission denied): {file_path}")
    except UnicodeDecodeError:
        # Try again with latin-1 as fallback
        with open(file_path, "r", encoding="latin-1") as fh:
            return fh.readlines()
