"""
test_interactive_session.py — Tests for the interactive debugging mode
"""

import pytest
from unittest.mock import patch, call
from src.interactive_session import DebugContext, start_interactive_session
from src.llm_engine import DebugAnalysis
from src.prompt_builder import build_follow_up_prompt

# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

MOCK_ANALYSIS = DebugAnalysis(
    error_explanation="List index 10 doesn't exist.",
    root_cause="List is too short.",
    suggested_fix="Check length.",
    corrected_code="if len(l) > 10: print(l[10])",
    model="deepseek-coder",
    parse_source="json"
)

MOCK_CONTEXT = DebugContext(
    error_type="IndexError",
    error_message="IndexError: list index out of range",
    file="app.py",
    line=5,
    code_context="l = [1, 2]\nprint(l[10])",
    initial_analysis=MOCK_ANALYSIS,
)


class TestPromptGeneration:
    def test_question_prompt_generation_contains_elements(self):
        """Verify the follow-up prompt contains context, error info, and the question."""
        ctx = DebugContext(
            error_type="IndexError",
            error_message="IndexError: list index out of range",
            file="app.py",
            line=5,
            code_context="l = [1, 2]",
            initial_analysis=MOCK_ANALYSIS,
        )
        
        question = "What is an index in python?"
        prompt = build_follow_up_prompt(ctx, question)
        
        assert "IndexError: list index out of range" in prompt
        assert "l = [1, 2]" in prompt
        assert "List index 10 doesn't exist." in prompt  # initial analysis 
        assert "What is an index in python?" in prompt
        assert "User Question:" in prompt

    def test_prompt_includes_history(self):
        ctx = DebugContext(
            error_type="IndexError",
            error_message="IndexError: out of range",
            file=None,
            line=None,
            code_context="l[10]",
            initial_analysis=MOCK_ANALYSIS,
            history=[("user", "why?"), ("assistant", "because")]
        )
        prompt = build_follow_up_prompt(ctx, "and then?")
        assert "User: why?" in prompt
        assert "Assistant: because" in prompt
        assert "User Question:\nand then?" in prompt


class TestSessionLoop:
    @patch("builtins.input", side_effect=["exit"])
    @patch("builtins.print")
    def test_exit_conditions_exit(self, mock_print, mock_input):
        """Verify the session exits immediately on 'exit'."""
        start_interactive_session(MOCK_CONTEXT, model="deepseek-coder")
        mock_input.assert_called_once()

    @patch("builtins.input", side_effect=["quit"])
    @patch("builtins.print")
    def test_exit_conditions_quit(self, mock_print, mock_input):
        """Verify the session exits immediately on 'quit'."""
        start_interactive_session(MOCK_CONTEXT, model="deepseek-coder")
        mock_input.assert_called_once()

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    @patch("builtins.print")
    def test_exit_conditions_ctrl_c(self, mock_print, mock_input):
        """Verify the session exits cleanly on Ctrl+C."""
        start_interactive_session(MOCK_CONTEXT, model="deepseek-coder")
        mock_input.assert_called_once()
        # Verify we print Session ended.
        mock_print.assert_any_call("\nSession ended.")

    @patch("src.interactive_session.generate_followup", return_value="Here is the fix.")
    @patch("builtins.input", side_effect=["How do I fix this?", "exit"])
    @patch("builtins.print")
    def test_llm_response_handling(self, mock_print, mock_input, mock_generate):
        """Verify the LLM is called and history is updated."""
        # Use a fresh context so history is empty
        ctx = DebugContext(**MOCK_CONTEXT.__dict__.copy())
        ctx.history = []
        
        start_interactive_session(ctx, model="deepseek-coder")
        
        # Verify generation was called
        mock_generate.assert_called_once()
        assert "How do I fix this?" in mock_generate.call_args[0][0]
        assert mock_generate.call_args[1]["model"] == "deepseek-coder"
        
        # Verify history was updated
        assert len(ctx.history) == 2
        assert ctx.history[0] == ("user", "How do I fix this?")
        assert ctx.history[1] == ("assistant", "Here is the fix.")
        
        # Verify it printed the answer
        mock_print.assert_any_call("Here is the fix.\n")
