import pytest
from unittest.mock import patch, Mock
import httpx
from connection import LLMBackend, check_llm_backend, _check_ollama, _check_vllm, list_available_models


class TestLLMBackendChecks:
    """Test LLM backend connectivity checks."""
    
    @patch('httpx.get')
    def test_check_ollama_success(self, mock_get):
        """Test successful Ollama connection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert _check_ollama() is True
        mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5.0)
    
    @patch('httpx.get')
    def test_check_ollama_failure(self, mock_get):
        """Test failed Ollama connection."""
        mock_get.side_effect = httpx.RequestError("Connection failed")
        
        assert _check_ollama() is False
    
    @patch('httpx.get')
    def test_check_vllm_success(self, mock_get):
        """Test successful vLLM connection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert _check_vllm() is True
        mock_get.assert_called_once_with("http://localhost:8000/v1/models", timeout=5.0)
    
    @patch('httpx.get')
    def test_check_vllm_failure(self, mock_get):
        """Test failed vLLM connection."""
        mock_get.side_effect = httpx.TimeoutException("Timeout")
        
        assert _check_vllm() is False
    
    def test_check_llm_backend_ollama(self):
        """Test check_llm_backend for Ollama."""
        with patch('connection._check_ollama', return_value=True):
            assert check_llm_backend(LLMBackend.OLLAMA) is True
    
    def test_check_llm_backend_vllm(self):
        """Test check_llm_backend for vLLM."""
        with patch('connection._check_vllm', return_value=True):
            assert check_llm_backend(LLMBackend.VLLM) is True


class TestListAvailableModels:
    """Test listing available models."""
    
    @patch('httpx.get')
    def test_list_ollama_models(self, mock_get):
        """Test listing Ollama models."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "codellama:latest"},
                {"name": "llama2:latest"}
            ]
        }
        mock_get.return_value = mock_response
        
        models = list_available_models("ollama")
        assert models == ["codellama:latest", "llama2:latest"]
    
    @patch('httpx.get')
    def test_list_vllm_models(self, mock_get):
        """Test listing vLLM models."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "meta-llama/Llama-2-7b-chat-hf"},
                {"id": "codellama/CodeLlama-7b-Python-hf"}
            ]
        }
        mock_get.return_value = mock_response
        
        models = list_available_models("vllm")
        assert models == ["meta-llama/Llama-2-7b-chat-hf", "codellama/CodeLlama-7b-Python-hf"]
    
    @patch('httpx.get')
    def test_list_models_failure(self, mock_get):
        """Test listing models when connection fails."""
        mock_get.side_effect = httpx.RequestError("Connection failed")
        
        models = list_available_models("ollama")
        assert models is None