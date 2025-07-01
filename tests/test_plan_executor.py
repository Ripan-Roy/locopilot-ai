import pytest
import tempfile
import shutil
from pathlib import Path
import json

from locopilot.core.executor import PlanExecutor, PlanAction, ActionType


class TestPlanExecutor:
    """Test cases for the PlanExecutor class."""
    
    def setup_method(self):
        """Create a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_path = Path(self.temp_dir)
        self.executor = PlanExecutor(self.project_path, dry_run=False, interactive=False)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_file(self):
        """Test creating a new file."""
        action = PlanAction(
            action_type=ActionType.CREATE_FILE,
            target="test.txt",
            content="Hello, World!"
        )
        
        results = self.executor.execute_plan([action])
        
        assert results["success"]
        assert len(results["executed"]) == 1
        assert len(results["failed"]) == 0
        
        # Verify file was created
        file_path = self.project_path / "test.txt"
        assert file_path.exists()
        assert file_path.read_text() == "Hello, World!"
    
    def test_edit_file(self):
        """Test editing an existing file."""
        # First create a file
        file_path = self.project_path / "edit_test.txt"
        file_path.write_text("Original content")
        
        # Edit the file
        action = PlanAction(
            action_type=ActionType.EDIT_FILE,
            target="edit_test.txt",
            old_content="Original",
            new_content="Modified"
        )
        
        results = self.executor.execute_plan([action])
        
        assert results["success"]
        assert file_path.read_text() == "Modified content"
    
    def test_delete_file(self):
        """Test deleting a file."""
        # Create a file first
        file_path = self.project_path / "delete_me.txt"
        file_path.write_text("Delete this")
        
        action = PlanAction(
            action_type=ActionType.DELETE_FILE,
            target="delete_me.txt"
        )
        
        results = self.executor.execute_plan([action])
        
        assert results["success"]
        assert not file_path.exists()
    
    def test_create_directory(self):
        """Test creating a directory."""
        action = PlanAction(
            action_type=ActionType.CREATE_DIR,
            target="new_dir/sub_dir"
        )
        
        results = self.executor.execute_plan([action])
        
        assert results["success"]
        dir_path = self.project_path / "new_dir" / "sub_dir"
        assert dir_path.exists()
        assert dir_path.is_dir()
    
    def test_run_bash(self):
        """Test running a bash command."""
        action = PlanAction(
            action_type=ActionType.RUN_BASH,
            command="echo 'Test output' > bash_test.txt",
            target="bash"
        )
        
        results = self.executor.execute_plan([action])
        
        assert results["success"]
        file_path = self.project_path / "bash_test.txt"
        assert file_path.exists()
        assert "Test output" in file_path.read_text()
    
    def test_multiple_actions(self):
        """Test executing multiple actions in sequence."""
        actions = [
            PlanAction(
                action_type=ActionType.CREATE_DIR,
                target="project"
            ),
            PlanAction(
                action_type=ActionType.CREATE_FILE,
                target="project/main.py",
                content="print('Hello')"
            ),
            PlanAction(
                action_type=ActionType.CREATE_FILE,
                target="project/config.json",
                content='{"key": "value"}'
            ),
            PlanAction(
                action_type=ActionType.RUN_BASH,
                command="cd project && python main.py > output.txt",
                target="bash"
            )
        ]
        
        results = self.executor.execute_plan(actions)
        
        assert results["success"]
        assert len(results["executed"]) == 4
        
        # Verify all files were created
        assert (self.project_path / "project").exists()
        assert (self.project_path / "project" / "main.py").exists()
        assert (self.project_path / "project" / "config.json").exists()
        assert (self.project_path / "project" / "output.txt").exists()
    
    def test_rollback(self):
        """Test rollback functionality."""
        # Create a file
        action = PlanAction(
            action_type=ActionType.CREATE_FILE,
            target="rollback_test.txt",
            content="Test content"
        )
        
        results = self.executor.execute_plan([action])
        assert results["success"]
        
        file_path = self.project_path / "rollback_test.txt"
        assert file_path.exists()
        
        # Rollback
        self.executor.rollback()
        
        # File should be deleted
        assert not file_path.exists()
    
    def test_parse_text_plan(self):
        """Test parsing a text-based plan."""
        plan_text = """
        CREATE_FILE: test1.txt
        CREATE_DIR: test_dir
        EDIT_FILE: test2.txt
        RUN_BASH: echo "test"
        """
        
        actions = PlanExecutor.parse_plan_from_text(plan_text)
        
        assert len(actions) == 4
        assert actions[0].action_type == ActionType.CREATE_FILE
        assert actions[0].target == "test1.txt"
        assert actions[1].action_type == ActionType.CREATE_DIR
        assert actions[2].action_type == ActionType.EDIT_FILE
        assert actions[3].action_type == ActionType.RUN_BASH
        assert actions[3].command == 'echo "test"'
    
    def test_parse_json_plan(self):
        """Test parsing a JSON-based plan."""
        plan_json = {
            "actions": [
                {
                    "action_type": "create_file",
                    "target": "test.py",
                    "content": "print('hello')",
                    "description": "Create test file"
                },
                {
                    "action_type": "run_bash",
                    "target": "bash",
                    "command": "python test.py"
                }
            ]
        }
        
        actions = PlanExecutor.parse_plan_from_json(plan_json)
        
        assert len(actions) == 2
        assert actions[0].action_type == ActionType.CREATE_FILE
        assert actions[0].content == "print('hello')"
        assert actions[1].action_type == ActionType.RUN_BASH
        assert actions[1].command == "python test.py"
    
    def test_dry_run(self):
        """Test dry run mode."""
        executor = PlanExecutor(self.project_path, dry_run=True, interactive=False)
        
        action = PlanAction(
            action_type=ActionType.CREATE_FILE,
            target="dry_run_test.txt",
            content="Should not be created"
        )
        
        results = executor.execute_plan([action])
        
        # Action should be marked as executed
        assert len(results["executed"]) == 1
        
        # But file should not actually exist
        file_path = self.project_path / "dry_run_test.txt"
        assert not file_path.exists()
    
    def test_error_handling(self):
        """Test error handling for invalid actions."""
        # Try to edit a non-existent file
        action = PlanAction(
            action_type=ActionType.EDIT_FILE,
            target="non_existent.txt",
            content="New content"
        )
        
        results = self.executor.execute_plan([action])
        
        assert not results["success"]
        assert len(results["failed"]) == 1
        assert len(results["errors"]) == 1
        assert "not found" in results["errors"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])