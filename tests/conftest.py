import pytest
from unittest.mock import Mock, patch
import os


@pytest.fixture(autouse=True)
def mock_environment():
    """Mock environment variables for tests."""
    with patch.dict(os.environ, {
        'VLLM_API_BASE': 'http://localhost:8000',
        'OLLAMA_HOST': 'http://localhost:11434'
    }):
        yield


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama LLM client."""
    with patch('connection.OllamaLLM') as mock:
        client = Mock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_vllm_client():
    """Mock vLLM client."""
    with patch('connection.VLLMOpenAI') as mock:
        client = Mock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_httpx_get():
    """Mock httpx.get for API calls."""
    with patch('httpx.get') as mock:
        yield mock


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    return {
        "content": "This is a mock response",
        "model": "mock-model",
        "created_at": "2024-01-01T00:00:00Z",
        "done": True
    }