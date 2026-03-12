"""
test_prompt_builder.py — Tests for the Prompt Builder module
"""

import pytest
from src.parser import parse_error
from src.retriever import get_context
from src.prompt_builder import build_prompt, build_prompt_from_raw, OUTPUT_SCHEMA


TYPE_ERROR_TRACE = """\
Traceback (most recent call last):
  File "main.py", line 10, in <module>
    result = 5 + "hello"
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""

SAMPLE_CODE = """\
def add(a, b):
    return a + b

def main():
    x = 5
    y = "hello"
    result = x + y
    print(result)

if __name__ == "__main__":
    main()
"""


@pytest.fixture
def parsed_error():
    return parse_error(TYPE_ERROR_TRACE)


@pytest.fixture
def code_context():
    return get_context(code_string=SAMPLE_CODE, line_number=7)


@pytest.fixture
def prompt(parsed_error, code_context):
    return build_prompt(parsed_error, code_context)


class TestPromptStructure:
    def test_prompt_is_string(self, prompt):
        assert isinstance(prompt, str)

    def test_prompt_not_empty(self, prompt):
        assert len(prompt) > 100

    def test_contains_error_type(self, prompt):
        assert "TypeError" in prompt

    def test_contains_error_message(self, prompt):
        assert "unsupported operand" in prompt

    def test_contains_file_reference(self, prompt):
        assert "main.py" in prompt

    def test_contains_line_number(self, prompt):
        assert "10" in prompt

    def test_contains_code_section(self, prompt):
        assert "CODE CONTEXT" in prompt

    def test_contains_stack_trace_section(self, prompt):
        assert "STACK TRACE" in prompt

    def test_contains_error_section(self, prompt):
        assert "ERROR INFORMATION" in prompt

    def test_contains_task_section(self, prompt):
        assert "YOUR TASK" in prompt

    def test_contains_json_schema(self, prompt):
        assert "error_explanation" in prompt
        assert "root_cause" in prompt
        assert "suggested_fix" in prompt
        assert "corrected_code" in prompt

    def test_contains_code_snippet(self, prompt):
        assert "result = x + y" in prompt

    def test_error_line_marked(self, prompt):
        """The >>> marker for error line should be in the prompt"""
        assert ">>>" in prompt

    def test_json_only_instruction(self, prompt):
        """Prompt must explicitly ask for JSON-only output"""
        assert "JSON" in prompt


class TestRawPromptBuilder:
    def test_build_from_raw_strings(self):
        prompt = build_prompt_from_raw(
            error_message=TYPE_ERROR_TRACE,
            code_snippet=SAMPLE_CODE,
        )
        assert isinstance(prompt, str)
        assert "TypeError" in prompt
        assert "error_explanation" in prompt

    def test_raw_builder_no_empty(self):
        prompt = build_prompt_from_raw(
            error_message=TYPE_ERROR_TRACE,
            code_snippet=SAMPLE_CODE,
        )
        assert len(prompt) > 50


class TestPromptFormatting:
    def test_prompt_has_sections_in_order(self, prompt):
        """Key sections should appear in correct order"""
        error_idx = prompt.index("ERROR INFORMATION")
        code_idx = prompt.index("CODE CONTEXT")
        task_idx = prompt.index("YOUR TASK")
        assert error_idx < code_idx < task_idx

    def test_no_file_path_when_missing(self):
        """When error has no file, prompt should still build"""
        err = parse_error("RuntimeError: something broke")
        ctx = get_context(code_string="x = 1\n")
        prompt = build_prompt(err, ctx)
        assert "RuntimeError" in prompt
        assert isinstance(prompt, str)
