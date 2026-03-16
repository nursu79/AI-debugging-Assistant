"""
interactive_session.py — Interactive Debugging Mode

Manages the conversation loop for follow-up questions about an error
that has already been analyzed.
"""

import sys
from dataclasses import dataclass, field
from src.llm_engine import DebugAnalysis, generate_followup
from src.prompt_builder import build_follow_up_prompt

@dataclass
class DebugContext:
    """Stores the context of the debugging session."""
    error_type: str
    error_message: str
    file: str | None
    line: int | None
    code_context: str
    initial_analysis: DebugAnalysis
    history: list[tuple[str, str]] = field(default_factory=list)


def start_interactive_session(context: DebugContext, model: str) -> None:
    """
    Start a CLI loop for follow-up questions about the error.
    
    Args:
        context: The initialized DebugContext.
        model:   The Ollama model to use.
    """
    print("\n" + "═" * 60)
    print("  INTERACTIVE DEBUGGING MODE")
    print("═" * 60)
    print("Initial analysis complete. You can now ask follow-up questions.")
    print("Type 'exit', 'quit', or press Ctrl+C to end the session.\n")

    while True:
        try:
            # Read user input
            question = input("> ").strip()
            
            # Check exit conditions
            if question.lower() in ("exit", "quit"):
                print("Session ended.")
                break
            
            if not question:
                continue

            # Build the follow-up prompt
            prompt = build_follow_up_prompt(context, question)

            # Get the answer from the LLM
            print("\nAssistant:")
            answer = generate_followup(prompt, model=model)
            print(answer + "\n")

            # Update history (keep last 5 interactions to avoid context limit)
            context.history.append(("user", question))
            context.history.append(("assistant", answer))
            if len(context.history) > 10:
                context.history = context.history[-10:]

        except KeyboardInterrupt:
            print("\nSession ended.")
            break
        except Exception as e:
            print(f"\n❌ Error generating response: {e}\n", file=sys.stderr)
