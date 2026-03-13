# Design Decisions

This document outlines the architectural choices and reasoning I've followed for the AI Debugging Assistant.

## 1. Model Choice: DeepSeek-Coder

I chose **DeepSeek-Coder-6.7B** as the primary model for this assistant for several reasons:
- **State-of-the-Art Coding Performance:** DeepSeek-Coder consistently outperforms larger models in Python code generation and reasoning tasks.
- **Strict Instruction Following:** It is highly responsive to system prompts, making it ideal for generating structured JSON output.
- **Local Efficiency:** The 6.7B parameter version runs smoothly on local hardware via Ollama, ensuring privacy and zero latency costs.

## 2. Structured Prompts

Instead of open-ended questions, I implemented a **structured, section-based prompt**:
- **Why?** LLMs perform better when the context is clearly demarcated. By separating "ERROR INFORMATION", "STACK TRACE", and "CODE CONTEXT", I help the model "pay attention" to the right details.
- **Control:** Explicitly defining the "YOUR TASK" and "OUTPUT SCHEMA" sections minimizes conversational filler and forces the model into a problem-solving mode.

## 3. Hallucination Mitigation

Hallucination in debugging is dangerous (suggesting non-existent libraries or incorrect fixes). I mitigate this through:
- **Low Temperature (0.1):** I set the model temperature to 0.1 to favor deterministic, grounded responses over creative ones.
- **Annotated Context:** By marking the exact error line with `>>>`, I prevent the LLM from fixing the "wrong" part of the file.
- **Multi-Strategy Parsing:**
    1. **Direct JSON:** I instruct the model to return JSON-only.
    2. **Block Extraction:** If the model adds prose, I extract the JSON block from markdown fences (` ```json `).
    3. **Regex Fallback:** If the JSON structure is broken but the keys are present in plain text, I use regex to salvage the explanation and fix.

## 4. Pipeline Orchestration

I designed the system as a **functional pipeline** rather than a monolith:
- `parser.py` is pure regex; it doesn't need the LLM.
- `retriever.py` is pure I/O; it doesn't need the LLM.
- `prompt_builder.py` is pure string templating.
This modularity makes the system **highly testable** (as seen in my 90+ test suite) and allows for replacing components (e.g., switching from Ollama to OpenAI) with minimal changes.

## 5. System Limitations

- **Single-File Focus:** Currently, the retriever only fetches context from the file mentioned in the stack trace. It does not resolve imports across the whole project.
- **Language Support:** While the logic is general, I have tuned the `ErrorParser` specifically for Python's `traceback` format.
