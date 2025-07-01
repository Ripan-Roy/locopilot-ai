import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from rich.console import Console
from rich.text import Text
from rich.panel import Panel


console = Console()


def ensure_config_dir(project_path: Path) -> Path:
    """Ensure .locopilot config directory exists."""
    config_dir = project_path / ".locopilot"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {}
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def save_config(config_path: Path, config: Dict[str, Any]):
    """Save configuration to YAML file."""
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def print_banner():
    """Print Locopilot ASCII banner."""
    banner = r"""
    __                        _ __      __ 
   / /  ____  _________  ____(_) /___  / /_
  / /  / __ \/ ___/ __ \/ __ / / / __ \/ __/
 / /__/ /_/ / /__/ /_/ / /_/ / / / /_/ / /_  
/____/\____/\___/\____/ .___/_/_/\____/\__/  
                     /_/                      
    """
    console.print(Text(banner, style="bold cyan"))
    console.print("Local-first, agentic coding assistant\n", style="dim")


def get_project_files(
    project_path: Path,
    extensions: Optional[List[str]] = None,
    ignore_patterns: Optional[List[str]] = None
) -> List[Path]:
    """Get all relevant files in the project."""
    
    if extensions is None:
        extensions = [
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
            '.h', '.hpp', '.cs', '.rb', '.go', '.rs', '.php', '.swift',
            '.kt', '.scala', '.r', '.m', '.mm', '.sh', '.bash', '.zsh',
            '.yml', '.yaml', '.json', '.xml', '.toml', '.ini', '.cfg',
            '.md', '.rst', '.txt'
        ]
    
    if ignore_patterns is None:
        ignore_patterns = [
            '__pycache__', '.git', '.venv', 'venv', 'env',
            'node_modules', 'dist', 'build', '.pytest_cache',
            '.mypy_cache', '.coverage', '*.pyc', '*.pyo',
            '.DS_Store', '.locopilot'
        ]
    
    files = []
    
    for item in project_path.rglob('*'):
        # Skip if matches ignore pattern
        if any(pattern in str(item) for pattern in ignore_patterns):
            continue
        
        # Only include files with specified extensions
        if item.is_file() and item.suffix in extensions:
            files.append(item)
    
    return sorted(files)


def read_file_content(file_path: Path, max_lines: int = 1000) -> str:
    """Read file content with size limit."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:max_lines]
            content = ''.join(lines)
            
            if len(lines) == max_lines:
                content += f"\n... (truncated at {max_lines} lines)"
            
            return content
    except Exception as e:
        return f"Error reading file: {e}"


def format_file_tree(project_path: Path, max_depth: int = 3) -> str:
    """Format project structure as a tree."""
    tree_lines = [f"📁 {project_path.name}/"]
    
    def add_tree_level(path: Path, prefix: str = "", depth: int = 0):
        if depth >= max_depth:
            return
        
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        
        for i, item in enumerate(items):
            # Skip hidden and ignored items
            if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules']:
                continue
            
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            next_prefix = "    " if is_last else "│   "
            
            if item.is_dir():
                tree_lines.append(f"{prefix}{current_prefix}📁 {item.name}/")
                add_tree_level(item, prefix + next_prefix, depth + 1)
            else:
                icon = "📄" if item.suffix in ['.py', '.js', '.ts'] else "📃"
                tree_lines.append(f"{prefix}{current_prefix}{icon} {item.name}")
    
    add_tree_level(project_path)
    return '\n'.join(tree_lines)


def create_file_edit_prompt(
    file_path: Path,
    task: str,
    current_content: Optional[str] = None
) -> str:
    """Create a prompt for file editing tasks."""
    
    prompt = f"Task: {task}\n\n"
    prompt += f"File: {file_path}\n\n"
    
    if current_content:
        prompt += "Current content:\n"
        prompt += "```\n"
        prompt += current_content
        prompt += "\n```\n\n"
    
    prompt += "Please provide the updated file content that accomplishes the task."
    
    return prompt