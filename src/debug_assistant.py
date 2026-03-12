"""
debug_assistant.py — Full Debugging Pipeline + CLI

Orchestrates all components:
  parse_error → get_context → build_prompt → analyze_error → DebugAnalysis

Can be used:
  - As a library: from src.debug_assistant import run_debug_pipeline
  - As a CLI:     python -m src.debug_assistant --error "..." --file path/to/code.py
"""

import argparse
import json
import sys
from typing import Optional

from src.parser import parse_error, ErrorMetadata
from src.retriever import get_context, CodeContext
from src.prompt_builder import build_prompt
from src.llm_engine import analyze_error, DebugAnalysis, is_ollama_running


# ---------------------------------------------------------------------------
# Public pipeline function
# ---------------------------------------------------------------------------

def run_debug_pipeline(
    error_message: str,
    code: Optional[str] = None,
    file_path: Optional[str] = None,
    model: str = "deepseek-coder",
    window_size: int = 5,
) -> dict:
    """
    Run the full debugging pipeline end-to-end.

    Args:
        error_message: Raw error / traceback string.
        code:          Raw code string (mutually exclusive with file_path).
        file_path:     Path to a source file on disk.
        model:         Ollama model name.
        window_size:   Lines of context around the error line.

    Returns:
        dict with keys: error_explanation, root_cause, suggested_fix, corrected_code
        plus metadata: error_type, file, line, parse_source.

    Raises:
        ValueError:       If neither code nor file_path is supplied.
        ConnectionError:  If Ollama is not reachable.
    """
    if code is None and file_path is None:
        raise ValueError("Provide either 'code' (string) or 'file_path'.")

    # ── Step 1: Parse the error ─────────────────────────────────────────────
    error_meta: ErrorMetadata = parse_error(error_message)

    # ── Step 2: Retrieve code context ───────────────────────────────────────
    code_ctx: CodeContext = get_context(
        file_path=file_path,
        code_string=code,
        line_number=error_meta.line,
        window_size=window_size,
    )

    # ── Step 3: Build prompt ─────────────────────────────────────────────────
    prompt = build_prompt(error_meta, code_ctx)

    # ── Step 4: Call LLM ─────────────────────────────────────────────────────
    analysis: DebugAnalysis = analyze_error(prompt, model=model)

    # ── Step 5: Return structured result ────────────────────────────────────
    result = analysis.to_dict()
    result["metadata"] = {
        "error_type": error_meta.error_type,
        "file": error_meta.file,
        "line": error_meta.line,
        "model": analysis.model,
        "parse_source": analysis.parse_source,
    }
    return result


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.debug_assistant",
        description="AI Debugging Assistant — analyze Python runtime errors",
    )
    parser.add_argument(
        "--error", "-e",
        required=True,
        help="Runtime error message or stack trace (use quotes)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file", "-f",
        metavar="FILE",
        help="Path to the Python source file",
    )
    group.add_argument(
        "--code", "-c",
        metavar="CODE",
        help="Inline code snippet as a string",
    )
    parser.add_argument(
        "--model", "-m",
        default="deepseek-coder",
        help="Ollama model to use (default: deepseek-coder)",
    )
    parser.add_argument(
        "--window", "-w",
        type=int,
        default=5,
        help="Lines of context around the error line (default: 5)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output raw JSON only (machine-readable)",
    )
    return parser


def _pretty_print(result: dict) -> None:
    """Print a human-readable debugging report."""
    meta = result.get("_meta", {})
    sep = "─" * 60

    print(f"\n{'═' * 60}")
    print("  AI DEBUGGING ASSISTANT — ANALYSIS REPORT")
    print(f"{'═' * 60}")

    print(f"\n► Error Type : {meta.get('error_type', 'Unknown')}")
    if meta.get("file"):
        print(f"► File       : {meta['file']}  (line {meta.get('line', '?')})")
    print(f"► Model      : {meta.get('model', 'unknown')}  "
          f"[parsed via {meta.get('parse_source', '?')}]\n")

    print(sep)
    print("📖  ERROR EXPLANATION")
    print(sep)
    print(result.get("error_explanation", "—"))

    print(f"\n{sep}")
    print("🔍  ROOT CAUSE")
    print(sep)
    print(result.get("root_cause", "—"))

    print(f"\n{sep}")
    print("🔧  SUGGESTED FIX")
    print(sep)
    print(result.get("suggested_fix", "—"))

    print(f"\n{sep}")
    print("✅  CORRECTED CODE")
    print(sep)
    print(result.get("corrected_code", "—"))
    print()


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # Check Ollama before doing anything expensive
    if not is_ollama_running():
        print(
            "❌  Ollama is not running. Start it with: ollama serve",
            file=sys.stderr,
        )
        return 1

    try:
        result = run_debug_pipeline(
            error_message=args.error,
            code=args.code,
            file_path=args.file,
            model=args.model,
            window_size=args.window,
        )
    except (ValueError, ConnectionError, RuntimeError) as exc:
        print(f"❌  {exc}", file=sys.stderr)
        return 1

    if args.json_only:
        # Remove internal metadata key for clean machine output
        out = {k: v for k, v in result.items() if k != "metadata"}
        print(json.dumps(out, indent=2))
    else:
        _pretty_print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
