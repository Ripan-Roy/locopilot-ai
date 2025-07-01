import os
from enum import Enum
from typing import Optional
import httpx
from langchain_ollama import OllamaLLM
from langchain_core.language_models import BaseLanguageModel


class LLMBackend(Enum):
    OLLAMA = "ollama"


def check_llm_backend(backend: LLMBackend) -> bool:
    """Check if the specified LLM backend is running and accessible."""
    
    if backend == LLMBackend.OLLAMA:
        return _check_ollama()
    else:
        return False


def _check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False



def get_llm_client(
    backend: str,
    model: str,
    temperature: float = 0.1,
    **kwargs
) -> BaseLanguageModel:
    """Get the appropriate LLM client based on backend."""
    
    backend_enum = LLMBackend(backend)
    
    if backend_enum == LLMBackend.OLLAMA:
        return OllamaLLM(
            model=model,
            temperature=temperature,
            base_url="http://localhost:11434",
            **kwargs
        )
    else:
        raise ValueError(f"Unsupported backend: {backend}")


def list_available_models(backend: str) -> Optional[list]:
    """List available models for the specified backend."""
    
    backend_enum = LLMBackend(backend)
    
    if backend_enum == LLMBackend.OLLAMA:
        try:
            response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
        except:
            pass
    
    return None