import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


class ActionType(Enum):
    CREATE_FILE = "create_file"
    EDIT_FILE = "edit_file"
    DELETE_FILE = "delete_file"
    RUN_BASH = "run_bash"
    CREATE_DIR = "create_dir"


@dataclass
class PlanAction:
    """Represents a single action in the execution plan."""
    action_type: ActionType
    target: str
    content: Optional[str] = None
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    command: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "target": self.target,
            "content": self.content,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "command": self.command,
            "description": self.description
        }


class PlanExecutor:
    """Executes a plan consisting of file operations and bash commands."""
    
    def __init__(self, project_path: Path, dry_run: bool = False, interactive: bool = True):
        self.project_path = project_path
        self.dry_run = dry_run
        self.interactive = interactive
        self.executed_actions: List[PlanAction] = []
        self.rollback_actions: List[PlanAction] = []
    
    def execute_plan(self, actions: List[PlanAction]) -> Dict[str, Any]:
        """Execute a list of planned actions."""
        results = {
            "success": True,
            "executed": [],
            "failed": [],
            "errors": []
        }
        
        for i, action in enumerate(actions):
            try:
                console.print(f"\n[cyan]Executing action {i+1}/{len(actions)}:[/cyan]")
                self._display_action(action)
                
                if not self.dry_run:
                    result = self._execute_action(action)
                    if result["success"]:
                        results["executed"].append(action.to_dict())
                        self.executed_actions.append(action)
                        console.print("[green]✓ Action completed successfully[/green]")
                    else:
                        results["failed"].append(action.to_dict())
                        results["errors"].append(result["error"])
                        console.print(f"[red]✗ Action failed: {result['error']}[/red]")
                        
                        if not self._should_continue_on_error():
                            results["success"] = False
                            break
                else:
                    console.print("[yellow]→ Dry run mode - action not executed[/yellow]")
                    results["executed"].append(action.to_dict())
                    
            except Exception as e:
                results["failed"].append(action.to_dict())
                results["errors"].append(str(e))
                results["success"] = False
                console.print(f"[red]✗ Unexpected error: {str(e)}[/red]")
                
                if not self._should_continue_on_error():
                    break
        
        return results
    
    def _execute_action(self, action: PlanAction) -> Dict[str, Any]:
        """Execute a single action based on its type."""
        try:
            if action.action_type == ActionType.CREATE_FILE:
                return self._create_file(action)
            elif action.action_type == ActionType.EDIT_FILE:
                return self._edit_file(action)
            elif action.action_type == ActionType.DELETE_FILE:
                return self._delete_file(action)
            elif action.action_type == ActionType.RUN_BASH:
                return self._run_bash(action)
            elif action.action_type == ActionType.CREATE_DIR:
                return self._create_directory(action)
            else:
                return {"success": False, "error": f"Unknown action type: {action.action_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _create_file(self, action: PlanAction) -> Dict[str, Any]:
        """Create a new file with content."""
        file_path = self._resolve_path(action.target)
        
        if file_path.exists():
            return {"success": False, "error": f"File already exists: {file_path}"}
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(action.content or "")
            
            self.rollback_actions.append(PlanAction(
                action_type=ActionType.DELETE_FILE,
                target=action.target
            ))
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _edit_file(self, action: PlanAction) -> Dict[str, Any]:
        """Edit an existing file."""
        file_path = self._resolve_path(action.target)
        
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        
        try:
            original_content = file_path.read_text()
            
            if action.old_content and action.new_content:
                new_content = original_content.replace(action.old_content, action.new_content)
            elif action.content:
                new_content = action.content
            else:
                return {"success": False, "error": "No content provided for edit"}
            
            file_path.write_text(new_content)
            
            self.rollback_actions.append(PlanAction(
                action_type=ActionType.EDIT_FILE,
                target=action.target,
                content=original_content
            ))
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _delete_file(self, action: PlanAction) -> Dict[str, Any]:
        """Delete a file."""
        file_path = self._resolve_path(action.target)
        
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        
        try:
            # Try to read as text first, fall back to binary
            try:
                original_content = file_path.read_text()
                is_binary = False
            except UnicodeDecodeError:
                # File is binary, read as bytes
                original_content = file_path.read_bytes()
                is_binary = True
            
            file_path.unlink()
            
            # For rollback, we'll skip binary files for now
            if not is_binary:
                self.rollback_actions.append(PlanAction(
                    action_type=ActionType.CREATE_FILE,
                    target=action.target,
                    content=original_content
                ))
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _create_directory(self, action: PlanAction) -> Dict[str, Any]:
        """Create a directory."""
        dir_path = self._resolve_path(action.target)
        
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_bash(self, action: PlanAction) -> Dict[str, Any]:
        """Execute a bash command."""
        if not action.command:
            return {"success": False, "error": "No command provided"}
        
        try:
            result = subprocess.run(
                action.command,
                shell=True,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            else:
                return {
                    "success": False,
                    "error": f"Command failed with exit code {result.returncode}",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out after 60 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _resolve_path(self, target: str) -> Path:
        """Resolve a target path relative to project root."""
        path = Path(target)
        if path.is_absolute():
            return path
        return self.project_path / path
    
    def _display_action(self, action: PlanAction):
        """Display action details to console."""
        if action.description:
            console.print(f"[bold]{action.description}[/bold]")
        
        if action.action_type == ActionType.CREATE_FILE:
            console.print(f"  → Creating file: [green]{action.target}[/green]")
            if action.content and len(action.content) < 500:
                syntax = Syntax(action.content, "python", theme="monokai", line_numbers=True)
                console.print(Panel(syntax, title="Content", expand=False))
        
        elif action.action_type == ActionType.EDIT_FILE:
            console.print(f"  → Editing file: [yellow]{action.target}[/yellow]")
            if action.old_content and action.new_content:
                console.print("  → Replacing content")
        
        elif action.action_type == ActionType.DELETE_FILE:
            console.print(f"  → Deleting file: [red]{action.target}[/red]")
        
        elif action.action_type == ActionType.RUN_BASH:
            console.print(f"  → Running command: [cyan]{action.command}[/cyan]")
        
        elif action.action_type == ActionType.CREATE_DIR:
            console.print(f"  → Creating directory: [green]{action.target}[/green]")
    
    def _should_continue_on_error(self) -> bool:
        """Ask user whether to continue after an error."""
        if self.dry_run or not self.interactive:
            return False
        
        response = console.input("\n[yellow]Continue with remaining actions? (y/n): [/yellow]")
        return response.lower() == 'y'
    
    def rollback(self):
        """Rollback executed actions."""
        if not self.rollback_actions:
            console.print("[yellow]No actions to rollback[/yellow]")
            return
        
        console.print("\n[bold red]Rolling back changes...[/bold red]")
        
        for action in reversed(self.rollback_actions):
            try:
                self._execute_action(action)
                console.print(f"[green]✓ Rolled back: {action.target}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Failed to rollback {action.target}: {str(e)}[/red]")
    
    @staticmethod
    def parse_plan_from_text(plan_text: str) -> List[PlanAction]:
        """Parse a text-based plan into PlanAction objects."""
        actions = []
        lines = plan_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if line.startswith('CREATE_FILE:'):
                target = line.replace('CREATE_FILE:', '').strip()
                actions.append(PlanAction(
                    action_type=ActionType.CREATE_FILE,
                    target=target,
                    description=f"Create file: {target}"
                ))
            
            elif line.startswith('EDIT_FILE:'):
                target = line.replace('EDIT_FILE:', '').strip()
                actions.append(PlanAction(
                    action_type=ActionType.EDIT_FILE,
                    target=target,
                    description=f"Edit file: {target}"
                ))
            
            elif line.startswith('RUN_BASH:'):
                command = line.replace('RUN_BASH:', '').strip()
                actions.append(PlanAction(
                    action_type=ActionType.RUN_BASH,
                    command=command,
                    target="bash",
                    description=f"Run command: {command}"
                ))
            
            elif line.startswith('CREATE_DIR:'):
                target = line.replace('CREATE_DIR:', '').strip()
                actions.append(PlanAction(
                    action_type=ActionType.CREATE_DIR,
                    target=target,
                    description=f"Create directory: {target}"
                ))
        
        return actions
    
    @staticmethod
    def parse_plan_from_json(plan_json: Union[str, Dict]) -> List[PlanAction]:
        """Parse a JSON-based plan into PlanAction objects."""
        if isinstance(plan_json, str):
            plan_data = json.loads(plan_json)
        else:
            plan_data = plan_json
        
        actions = []
        for item in plan_data.get("actions", []):
            action_type = ActionType(item["action_type"])
            actions.append(PlanAction(
                action_type=action_type,
                target=item.get("target", ""),
                content=item.get("content"),
                old_content=item.get("old_content"),
                new_content=item.get("new_content"),
                command=item.get("command"),
                description=item.get("description")
            ))
        
        return actions