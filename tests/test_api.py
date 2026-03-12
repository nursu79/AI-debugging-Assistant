"""
test_api.py — Integration tests for the FastAPI endpoint
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.api import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

VALID_REQUEST = {
    "error_message": "ZeroDivisionError: division by zero\nFile \"calc.py\", line 3",
    "code": "def div(x, y):\n    return x / y\ndiv(1, 0)",
    "model": "deepseek-coder"
}

MOCK_PIPELINE_RESULT = {
    "error_explanation": "Zero division error.",
    "root_cause": "y is 0.",
    "suggested_fix": "Check y.",
    "corrected_code": "return x / y if y != 0 else 0",
    "metadata": {
        "error_type": "ZeroDivisionError",
        "file": "calc.py",
        "line": 3,
        "model": "deepseek-coder",
        "parse_source": "json"
    }
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_read_root():
    """Test health check endpoint."""
    with patch("src.api.is_ollama_running", return_value=True):
        with patch("src.api.list_available_models", return_value=["deepseek-coder"]):
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "online"
            assert data["ollama_connected"] is True


@patch("src.api.is_ollama_running", return_value=True)
@patch("src.api.run_debug_pipeline")
def test_debug_endpoint_success(mock_pipeline, mock_running):
    """Test successful POST /debug call."""
    mock_pipeline.return_value = MOCK_PIPELINE_RESULT
    
    response = client.post("/debug", json=VALID_REQUEST)
    
    assert response.status_code == 200
    data = response.json()
    assert data["error_explanation"] == MOCK_PIPELINE_RESULT["error_explanation"]
    assert data["metadata"]["error_type"] == "ZeroDivisionError"


@patch("src.api.is_ollama_running", return_value=False)
def test_debug_endpoint_ollama_offline(mock_running):
    """Test 503 error when Ollama is offline."""
    response = client.post("/debug", json=VALID_REQUEST)
    assert response.status_code == 503
    assert "Ollama server is not reachable" in response.json()["detail"]


@patch("src.api.is_ollama_running", return_value=True)
def test_debug_endpoint_invalid_request(mock_running):
    """Test 422 error on missing required fields."""
    response = client.post("/debug", json={})
    assert response.status_code == 422


@patch("src.api.is_ollama_running", return_value=True)
@patch("src.api.run_debug_pipeline", side_effect=ValueError("Invalid traceback"))
def test_debug_endpoint_pipeline_error(mock_pipeline, mock_running):
    """Test 400 error when pipeline raises ValueError."""
    response = client.post("/debug", json=VALID_REQUEST)
    assert response.status_code == 400
    assert "Invalid traceback" in response.json()["detail"]
