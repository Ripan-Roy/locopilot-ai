import pytest
from pathlib import Path
from locopilot.llm.connection import LLMBackend, check_llm_backend
from locopilot.utils.file_ops import ensure_config_dir, get_project_files
from locopilot.core.memory import SessionState, LocopilotMemory


def test_session_state():
    """Test SessionState functionality."""
    state = SessionState()
    assert state.mode == "do"
    
    state.update(mode="refactor", model="codellama")
    assert state.mode == "refactor"
    assert state.model == "codellama"


def test_ensure_config_dir(tmp_path):
    """Test config directory creation."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    
    config_dir = ensure_config_dir(project_path)
    assert config_dir.exists()
    assert config_dir.name == ".locopilot"


def test_get_project_files(tmp_path):
    """Test project file scanning."""
    # Create test files
    (tmp_path / "test.py").write_text("print('test')")
    (tmp_path / "test.js").write_text("console.log('test')")
    (tmp_path / "readme.md").write_text("# Test")
    (tmp_path / "data.json").write_text('{"test": true}')
    
    # Create ignored directory
    ignored_dir = tmp_path / "__pycache__"
    ignored_dir.mkdir()
    (ignored_dir / "test.pyc").write_text("compiled")
    
    files = get_project_files(tmp_path)
    file_names = [f.name for f in files]
    
    assert "test.py" in file_names
    assert "test.js" in file_names
    assert "readme.md" in file_names
    assert "data.json" in file_names
    assert "test.pyc" not in file_names


def test_llm_backend_enum():
    """Test LLMBackend enum."""
    assert LLMBackend.OLLAMA.value == "ollama"
