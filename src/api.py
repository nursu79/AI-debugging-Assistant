"""
api.py — FastAPI Interface for AI Debugging Assistant

Exposes the debugging pipeline as a RESTful API.
Endpoint: POST /debug
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from src.debug_assistant import run_debug_pipeline
from src.llm_engine import is_ollama_running, list_available_models

app = FastAPI(
    title="AI Debugging Assistant API",
    description="Analyze Python runtime errors and get AI-powered fixes",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DebugRequest(BaseModel):
    error_message: str = Field(..., description="The runtime error message or stack trace")
    code: Optional[str] = Field(None, description="Raw source code as a string")
    file_path: Optional[str] = Field(None, description="Path to the source file on disk")
    model: str = Field("deepseek-coder", description="Ollama model to use")
    window_size: int = Field(5, description="Lines of context around the error", ge=1, le=50)


class DebugResponse(BaseModel):
    error_explanation: str
    root_cause: str
    suggested_fix: str
    corrected_code: str
    metadata: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "status": "online",
        "ollama_connected": is_ollama_running(),
        "available_models": list_available_models(),
    }


@app.post("/debug", response_model=DebugResponse)
async def debug_error(request: DebugRequest):
    """
    Submit an error and code context for analysis.
    """
    if not is_ollama_running():
        raise HTTPException(status_code=503, detail="Ollama server is not reachable")

    try:
        result = run_debug_pipeline(
            error_message=request.error_message,
            code=request.code,
            file_path=request.file_path,
            model=request.model,
            window_size=request.window_size,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
