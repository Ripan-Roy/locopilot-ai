from pathlib import Path
from typing import Optional

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text

from locopilot.core.agent import LocopilotAgent
from locopilot.llm.connection import check_llm_backend, LLMBackend
from locopilot.utils.file_ops import ensure_config_dir, load_config, save_config, print_banner

app = typer.Typer(
    name="locopilot",
    help="Local-first, agentic coding assistant",
    add_completion=False,
)
console = Console()


@app.command()
def init(
    backend: Optional[str] = typer.Option(
        None,
        "--backend",
        "-b",
        help="LLM backend to use (ollama)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (e.g., codellama:latest, deepseek-coder:latest)",
    ),
    project_path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (defaults to current directory)",
    ),
):
    """Initialize Locopilot in your project and start the interactive shell."""

    print_banner()

    # Set project path
    project_path = project_path or Path.cwd()

    # Ensure config directory exists
    config_dir = ensure_config_dir(project_path)
    config_path = config_dir / "config.yaml"

    # Check for existing config
    existing_config = load_config(config_path) if config_path.exists() else {}

    # Determine backend
    if not backend:
        backend = existing_config.get("backend")
        if not backend:
            # Check if Ollama is available
            ollama_available = check_llm_backend(LLMBackend.OLLAMA)

            if ollama_available:
                backend = "ollama"
                console.print("[green][/green] Ollama detected and selected")
            else:
                console.print("[red][/red] No LLM backend detected!")
                console.print(
                    "Please start Ollama (ollama serve)")
                raise typer.Exit(1)

    # Validate backend
    backend_enum = LLMBackend(backend)
    if not check_llm_backend(backend_enum):
        console.print(f"[red][/red] {backend} is not running!")
        console.print(f"Please start {backend} server first")
        raise typer.Exit(1)

    # Determine model
    if not model:
        model = existing_config.get("model")
        if not model:
            if backend == "ollama":
                model = typer.prompt(
                    "Enter model name",
                    default="codellama:latest"
                )
            else:
                model = typer.prompt(
                    "Enter model name",
                    default="deepseek-coder-6.7b"
                )

    # Save config
    config = {
        "backend": backend,
        "model": model,
        "project_path": str(project_path),
        "mode": existing_config.get("mode", "do"),
        "memory": {
            "max_tokens": existing_config.get("memory", {}).get("max_tokens", 4000),
            "summarization_threshold": existing_config.get("memory", {}).get("summarization_threshold", 3000),
        }
    }
    save_config(config_path, config)

    console.print(
        f"[green][/green] Initialized Locopilot with {backend} backend and {model} model")
    console.print(
        f"[green][/green] Project context initialized at {project_path}")

    # Start interactive shell
    _start_shell(config, project_path)


def _start_shell(config: dict, project_path: Path):
    """Start the interactive Locopilot shell."""

    # Initialize agent
    agent = LocopilotAgent(config, project_path)

    # Setup prompt session with history
    history_file = ensure_config_dir(project_path) / "history.txt"
    session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    console.print("\n[bold green]Locopilot Shell[/bold green]")
    console.print(
        f"Mode: [cyan]{config['mode']}[/cyan] | Model: [cyan]{config['model']}[/cyan]")
    console.print(
        "Type your task or use slash commands. Type /help for commands.\n")

    while True:
        try:
            # Get user input
            user_input = session.prompt("> ", multiline=False)

            if not user_input.strip():
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                result = agent.handle_slash_command(user_input)
                if result == "exit":
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                elif result:
                    console.print(result)
            else:
                # Process regular task with streaming
                full_response = ""

                # Create a panel for streaming content
                with Live(
                    Panel("", title="Locopilot", border_style="cyan"),
                    console=console,
                    refresh_per_second=10
                ) as live:
                    for chunk in agent.process_task_streaming(user_input):
                        full_response += chunk
                        # Update the live panel with current content
                        live.update(
                            Panel(full_response, title="Locopilot", border_style="cyan"))

                # Final newline for separation
                console.print()

        except KeyboardInterrupt:
            console.print(
                "\n[yellow]Use /end to exit or Ctrl+C again to force quit[/yellow]")
            try:
                continue
            except KeyboardInterrupt:
                console.print("\n[red]Force quit![/red]")
                break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            continue


@app.command()
def version():
    """Show Locopilot version."""
    console.print("Locopilot v0.1.3")


if __name__ == "__main__":
    app()
