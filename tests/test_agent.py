import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from locopilot.core.agent import LocopilotAgent


class TestLocopilotAgent:
    """Test LocopilotAgent functionality."""
    
    @patch('locopilot.core.agent.format_file_tree')
    @patch('locopilot.core.agent.get_project_files')
    @patch('locopilot.core.agent.get_llm_client')
    def test_agent_initialization(self, mock_get_llm_client, mock_get_project_files, mock_format_file_tree):
        """Test agent initialization."""
        mock_llm = Mock()
        mock_get_llm_client.return_value = mock_llm
        mock_get_project_files.return_value = []
        mock_format_file_tree.return_value = "mocked file tree"
        
        config = {
            "backend": "ollama",
            "model": "codellama",
            "temperature": 0.1,
            "memory": {
                "max_tokens": 4000,
                "summarization_threshold": 3000
            }
        }
        project_path = Path("/test/path")
        
        agent = LocopilotAgent(config=config, project_path=project_path)
        
        assert agent.config == config
        assert agent.project_path == project_path
        mock_get_llm_client.assert_called_once()
    
    @patch('locopilot.core.agent.format_file_tree')
    @patch('locopilot.core.agent.get_project_files')
    @patch('locopilot.core.agent.get_llm_client')
    @patch('locopilot.core.agent.LocopilotMemory')
    def test_agent_with_memory(self, mock_memory_class, mock_get_llm_client, mock_get_project_files, mock_format_file_tree):
        """Test agent with memory initialization."""
        mock_llm = Mock()
        mock_get_llm_client.return_value = mock_llm
        mock_memory = Mock()
        mock_memory_class.return_value = mock_memory
        mock_get_project_files.return_value = []
        mock_format_file_tree.return_value = "mocked file tree"
        
        config = {
            "backend": "ollama",
            "model": "llama2",
            "temperature": 0.2,
            "memory": {
                "max_tokens": 4000,
                "summarization_threshold": 3000
            }
        }
        project_path = Path("/test/path")
        
        agent = LocopilotAgent(config=config, project_path=project_path)
        
        # Verify memory is created with correct parameters
        mock_memory_class.assert_called_once_with(
            llm=mock_llm,
            max_token_limit=4000,
            summarization_threshold=3000
        )