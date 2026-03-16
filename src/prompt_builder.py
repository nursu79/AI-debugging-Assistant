"""
prompt_builder.py — Structured Prompt Builder

Builds a well-structured prompt for the LLM debugging analysis.
The prompt is designed to:
  - Give the LLM clear context about the error
  - Show the relevant code window
  - Instruct it to return structured JSON output
  - Reduce hallucinations via explicit output schema
"""

from src.parser import ErrorMetadata
from src.retriever import CodeContext

# Make sure not to cause circular dependency, so we only import for type hints if needed, 
# but here we can just use typing.Any for DebugContext if needed, or import from inside the function.


SYSTEM_INSTRUCTION = """\
You are an expert software debugging assistant specializing in Python runtime errors.
Your role is to analyze errors precisely, identify root causes, and provide actionable fixes.
Always respond with valid JSON only — no prose, no markdown fences, no extra text.\
"""

OUTPUT_SCHEMA = """\
{
  "error_explanation": "<clear explanation of what this error means>",
  "root_cause": "<specific reason why this error occurred in THIS code>",
  "suggested_fix": "<concrete step-by-step fix instructions>",
  "corrected_code": "<the corrected code snippet, ready to use>"
}\
"""


def build_prompt(
    error_metadata: ErrorMetadata,
    code_context: CodeContext,
) -> str:
    """
    Build a structured debugging prompt from parsed error metadata and code context.

    Args:
        error_metadata: Parsed error information from `parse_error()`.
        code_context:   Code window from `get_context()`.

    Returns:
        A formatted prompt string ready to be sent to the LLM.
    """
    sections = []

    # --- System role ---
    sections.append(SYSTEM_INSTRUCTION)
    sections.append("")

    # --- Error information ---
    sections.append("## ERROR INFORMATION")
    sections.append(f"Error Type    : {error_metadata.error_type}")
    sections.append(f"Error Message : {error_metadata.message}")
    if error_metadata.file:
        sections.append(f"File          : {error_metadata.file}")
    if error_metadata.line:
        sections.append(f"Line          : {error_metadata.line}")
    sections.append("")

    # --- Stack trace (if available) ---
    if error_metadata.stack_trace:
        sections.append("## STACK TRACE")
        sections.append("```")
        sections.append(error_metadata.stack_trace.strip())
        sections.append("```")
        sections.append("")

    # --- Code context ---
    sections.append("## CODE CONTEXT")
    sections.append(
        f"(Showing lines {code_context.start_line}–{code_context.end_line}"
        + (f" of {code_context.file_path}" if code_context.file_path else "")
        + ". The line marked with '>>>' is where the error occurred.)"
    )
    sections.append("```python")
    sections.append(code_context.snippet)
    sections.append("```")
    sections.append("")

    # --- Task ---
    sections.append("## YOUR TASK")
    sections.append(
        "Analyze the error and code context above. "
        "Respond ONLY with a single valid JSON object using exactly this schema:"
    )
    sections.append("")
    sections.append(OUTPUT_SCHEMA)

    return "\n".join(sections)


def build_prompt_from_raw(
    error_message: str,
    code_snippet: str,
) -> str:
    """
    Convenience builder for when we only have raw strings (API usage).

    Args:
        error_message: Raw error / traceback string.
        code_snippet:  Raw code string.

    Returns:
        A formatted prompt string.
    """
    from src.parser import parse_error
    from src.retriever import get_context

    error_metadata = parse_error(error_message)
    code_context = get_context(
        code_string=code_snippet,
        line_number=error_metadata.line,
    )
    return build_prompt(error_metadata, code_context)


def build_follow_up_prompt(context: "DebugContext", question: str) -> str:
    """
    Build a conversational prompt for follow-up debugging questions.

    Args:
        context:  The current DebugContext object holding the state.
        question: The user's new question.

    Returns:
        Structured prompt containing error summary, code snippet, initial analysis, and chat history.
    """
    sections = []

    sections.append("You are an AI debugging assistant. Answer clearly and concisely.")
    sections.append("")
    
    sections.append("## ERROR INFORMATION")
    sections.append(f"Type: {context.error_type}")
    sections.append(f"Message: {context.error_message}")
    sections.append("")
    
    sections.append("## CODE CONTEXT")
    sections.append("```python")
    sections.append(context.code_context)
    sections.append("```")
    sections.append("")
    
    sections.append("## INITIAL ANALYSIS")
    sections.append(f"Explanation: {context.initial_analysis.error_explanation}")
    sections.append(f"Root Cause: {context.initial_analysis.root_cause}")
    sections.append(f"Suggested Fix: {context.initial_analysis.suggested_fix}")
    sections.append("")
    
    if context.history:
        sections.append("## CONVERSATION HISTORY")
        for role, text in context.history:
            role_name = "User" if role == "user" else "Assistant"
            sections.append(f"{role_name}: {text}")
        sections.append("")

    sections.append("The user is asking a follow-up question about this error.")
    sections.append("")
    sections.append("User Question:")
    sections.append(question)

    return "\n".join(sections)
