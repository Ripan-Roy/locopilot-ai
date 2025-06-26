import os
from enum import Enum
from typing import Optional
import httpx
from langchain_ollama import OllamaLLM
from langchain_community.llms import VLLMOpenAI
from langchain_core.language_models import BaseLanguageModel


class LLMBackend(Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"


def check_llm_backend(backend: LLMBackend) -> bool:
    """Check if the specified LLM backend is running and accessible."""
    
    if backend == LLMBackend.OLLAMA:
        return _check_ollama()
    elif backend == LLMBackend.VLLM:
        return _check_vllm()
    else:
        return False


def _check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        return response.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False


def _check_vllm() -> bool:
    """Check if vLLM is running (OpenAI-compatible endpoint)."""
    vllm_url = os.getenv("VLLM_API_BASE", "http://localhost:8000")
    try:
        response = httpx.get(f"{vllm_url}/v1/models", timeout=5.0)
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
    elif backend_enum == LLMBackend.VLLM:
        vllm_url = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
        return VLLMOpenAI(
            model=model,
            temperature=temperature,
            openai_api_base=vllm_url,
            openai_api_key="dummy",  # vLLM doesn't need a real key
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
    elif backend_enum == LLMBackend.VLLM:
        vllm_url = os.getenv("VLLM_API_BASE", "http://localhost:8000")
        try:
            response = httpx.get(f"{vllm_url}/v1/models", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return [model["id"] for model in data.get("data", [])]
        except:
            pass
    
    return None