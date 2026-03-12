# AI Debugging Assistant

An AI-powered debugging assistant that helps developers understand and fix runtime errors using open-source LLMs via Ollama.

## Features

- **Structured Error Parsing** — Extracts `error_type`, `file`, `line`, and `message` from stack traces
- **Code Context Retrieval** — Fetches relevant lines around the error location
- **Intelligent Prompt Construction** — Builds structured prompts optimized for debugging tasks
- **LLM-Powered Analysis** — Integrates with Ollama (DeepSeek-Coder / CodeLlama)
- **Structured Output** — Returns validated JSON with explanation, root cause, fix, and corrected code
- **FastAPI Interface** — REST endpoint at `POST /debug`

## Architecture

```
User Input (error + code)
        │
        ▼
  Error Parser          ← parser.py
        │
        ▼
Code Context Retriever  ← retriever.py
        │
        ▼
  Prompt Builder        ← prompt_builder.py
        │
        ▼
   LLM Engine           ← llm_engine.py (Ollama)
        │
        ▼
Structured Response     ← debug_assistant.py
        │
        ▼
  FastAPI API           ← api.py
```

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running
- A code model pulled: `ollama pull deepseek-coder` or `ollama pull codellama`

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the API

```bash
uvicorn src.api:app --reload --port 8000
```

## API Usage

```bash
curl -X POST http://localhost:8000/debug \
  -H "Content-Type: application/json" \
  -d '{
    "error_message": "TypeError: unsupported operand type(s) for +: '\''int'\'' and '\''str'\''\nFile \"main.py\", line 10",
    "code": "result = 5 + \"hello\""
  }'
```

## Running Tests

```bash
pytest tests/ -v
```

## CLI Usage

```bash
python -m src.debug_assistant \
  --error "TypeError: unsupported operand type(s) for +: '\''int'\'' and '\''str'\''\nFile \"main.py\", line 10" \
  --file examples/sample_code.py
```

## Project Structure

```
ai-debug-assistant/
├── README.md
├── DESIGN_DECISIONS.md
├── requirements.txt
├── src/
│   ├── parser.py
│   ├── retriever.py
│   ├── prompt_builder.py
│   ├── llm_engine.py
│   ├── debug_assistant.py
│   └── api.py
├── tests/
│   ├── test_parser.py
│   ├── test_retriever.py
│   └── test_pipeline.py
└── examples/
    ├── sample_errors.txt
    └── sample_code.py
```

## Output Format

```json
{
  "error_explanation": "This error occurs when...",
  "root_cause": "The variable x is of type int but...",
  "suggested_fix": "Convert the string to int before adding...",
  "corrected_code": "result = 5 + int('hello')"
}
```

## Model Options

| Model | Command |
|-------|---------|
| DeepSeek-Coder (recommended) | `ollama pull deepseek-coder` |
| CodeLlama | `ollama pull codellama` |
| StarCoder2 | `ollama pull starcoder2` |
