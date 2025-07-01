# 🚀 Locopilot

[![PyPI version](https://badge.fury.io/py/locopilot.svg)](https://badge.fury.io/py/locopilot)
[![Python](https://img.shields.io/pypi/pyversions/locopilot.svg)](https://pypi.org/project/locopilot/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/Ripan-Roy/locopilot-ai.svg?style=social&label=Star)](https://github.com/Ripan-Roy/locopilot-ai)

<div align="center">
  <img src="assets/locopilot-demo.png" alt="Locopilot Demo" width="800"/>
</div>

Locopilot is an open-source, local-first, agentic coding assistant built for developers. It leverages local LLMs (via Ollama), and advanced memory management using LangGraph, to automate, plan, and edit codebases—all inside an interactive shell.

- **Private**: All code and prompts stay on your machine.
- **Agentic**: Locopilot plans, edits, iterates, and manages your coding tasks.
- **Interactive**: Drop into a shell, enter tasks or slash commands, and steer the agent in real time.
- **Memory-Efficient**: Advanced memory compression via LangGraph for "infinite" context.
- **Extensible**: Change models, modes, and add custom tools or plugins on the fly.

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Usage: Interactive Shell & Commands](#usage-interactive-shell--commands)
- [Project Structure](#project-structure)
- [Extensibility & Roadmap](#extensibility--roadmap)
- [Contributing](#contributing)
- [License](#license)

## ✨ Features

- **Local LLM Backend**: Bring your own Ollama server and code with any open-source LLM.
- **LangGraph Agent Workflow**: Plans, executes, edits, and compresses memory as a stateful, extensible graph.
- **Interactive Shell/REPL**: After init, drop into a chat-like agent terminal—just type coding tasks or slash commands.
- **Slash Command Support**: `/model`, `/change-mode`, `/concise`, `/clear`, `/new`, `/end`, `/help`, and more.
- **Smart Memory Compression**: Automatically summarizes previous context using the LLM itself, supporting ultra-long sessions.
- **Configurable**: Models, modes, and summarization thresholds are all runtime-editable.
- **Pluggable Nodes**: Add file tools, planning modules, git ops, and vector-based retrieval easily.
- **(Planned) Git Integration**: Auto-commit, rollback, and view code diffs per agent step.

## ⚡️ How It Works

### 1. Initialization
Run `locopilot init` in your project root.
- Locopilot checks Ollama, prompts for model, sets up `.locopilot/config.yaml`.
- You're dropped into an interactive agent shell (REPL).

### 2. Agentic Workflow (via LangGraph)
Each user input is parsed:
- **Slash command** (`/model`, etc.) → runs as a graph branch.
- **Normal prompt** (task) → plans, edits, summarizes via a workflow graph:
  ```
  User Task → [Planning Node] → [File Edit Node] → [Memory Summarizer Node] → (Repeat)
  ```
- Memory is managed with a LangGraph memory node—summarizing, chunking, and compressing context as needed.

### 3. Session Management
- Change models, modes, or reset memory on the fly with slash commands.
- All state (memory, model, mode) persists during the session.

## 🏗️ Architecture

Key components:

- **CLI Layer**: Typer-based CLI, launches shell (REPL), parses slash commands.
- **LangGraph Workflow**:
  - **Nodes**: Planning, file edit, summarization, slash command handler, etc.
  - **Edges**: Control session flow, branching between commands and prompts.
- **LLM Backend**:
  - **Ollama**: For running CodeLlama, DeepSeek, etc.
- **Memory Layer**:
  - LangChain/LangGraph memory objects (buffer, summary, vector, hybrid).
  - Summarizes old context using the LLM to avoid hitting token/window limits.
- **Config/Project Layer**:
  - `.locopilot/config.yaml` stores model/backend/session preferences.

### Stateful Graph Example:
```
               [User Input]
                      |
      +---------------+---------------+
      |                               |
 [Slash Command]              [Prompt/Task]
      |                               |
[Command Handler]   [Plan]->[Edit]->[Summarize]->[Memory]
      |                               |
     END                             Loop
```

## 🛠 Getting Started

### Requirements
- Python 3.8+
- Ollama running locally
- pip

### Install Locopilot

**Option 1: Install from PyPI (Recommended)**
```bash
pip install locopilot
```

**Option 2: Install from Source**
```bash
git clone https://github.com/Ripan-Roy/locopilot-ai.git
cd locopilot-backend
pip install -e .
```

### Start Your Local LLM

**Ollama:**
```bash
ollama serve
ollama pull codellama:latest
```

### Initialize and Enter the Agent Shell
```bash
locopilot init
```

This checks LLM backend, prompts for config, scans for project context, and launches the interactive shell.

## 🖥️ Usage: Interactive Shell & Commands

After init, Locopilot enters a shell where you can type prompts and commands:

### Example Session
```
$ locopilot init
[✓] Ollama running. Model: codellama:latest
[✓] Project context initialized.

Locopilot Shell (mode: do):
> Add OAuth login to my Django app
[PLANNING] ...
[EDITING] ...
[MEMORY] ...

> /model
Current model: codellama:latest
Enter new model: deepseek-coder:latest
[✓] Model switched to deepseek-coder:latest

> /change-mode
Current mode: do
Available modes: do, refactor, explain, chat
Enter new mode: refactor
[✓] Mode set to refactor.

> Refactor the payment logic for clarity
...

> /concise
[✓] Context summarized and compressed.

> /clear
[✓] Session memory cleared.

> /new
[✓] New session started.

> /end
[✓] Session ended. Bye!
```

### Supported Slash Commands

| Command | Purpose |
|---------|---------|
| `/model` | Change LLM model/backend for current session |
| `/change-mode` | Switch between do, refactor, explain, chat modes |
| `/clear` | Clear all current context/memory |
| `/new` | Start a new session/project |
| `/end` | End the agent shell and exit |
| `/concise` | Force summarization/compression of current context |
| `/help` | Show help and command list |

Anything not starting with `/` is treated as a task in the current mode!

## 🗂️ Project Structure

```
locopilot-backend/
├── locopilot/                  # Main package directory
│   ├── __init__.py
│   ├── core/                   # Core functionality
│   │   ├── __init__.py
│   │   ├── agent.py           # LangGraph workflow and nodes
│   │   ├── memory.py          # Session/context memory management
│   │   └── executor.py        # Plan execution engine
│   ├── llm/                    # LLM backend handling
│   │   ├── __init__.py
│   │   ├── connection.py      # Ollama connection helpers
│   │   └── backends/          # Backend-specific implementations
│   ├── cli/                    # CLI components
│   │   ├── __init__.py
│   │   ├── app.py             # CLI entrypoint, shell/REPL logic
│   │   └── commands/          # CLI command implementations
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       └── file_ops.py        # File operations, config helpers
├── tests/                      # Test suite
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_basic.py
│   ├── test_connection.py
│   └── test_plan_executor.py
├── scripts/                    # Setup and utility scripts
│   └── setup.sh
├── docs/                       # Documentation
├── assets/                     # Static assets
│   └── locopilot-demo.png
├── pyproject.toml             # Package configuration
├── requirements.txt           # Dependencies
├── README.md
└── LICENSE
```

## 🧠 Memory Management (with LangGraph)

- `ConversationBufferMemory` or `ConversationSummaryBufferMemory` is attached to the agent graph.
- As session context grows, old steps are summarized using the LLM and replaced in memory.
- This ensures Locopilot "remembers" key tasks, design decisions, and context for long sessions.
- Slash command `/concise` lets you summarize on demand.

## ⚡️ Extensibility & Roadmap

- **Editor Plugins**: VSCode, Vim, JetBrains, etc.
- **Project-Aware RAG**: Integrate vector DBs (Chroma, Qdrant) for smart codebase retrieval.
- **(Planned) Git Integration**: Auto-commit, diff, and rollback per step.
- **Save/Load Sessions**: `/save`, `/load`, `/history` commands.
- **Custom Plugins/Nodes**: Add your own LangGraph nodes for tools or workflows.
- **Web/GUI Frontends**: Same agent core, different interface.

## 🤝 Contributing

- Fork and PRs are welcome!
- Open issues for bugs or feature requests.
- For major features (graph nodes, memory backends), see CONTRIBUTING.md (coming soon).

## 📝 License

MIT License. Use, fork, and extend as you wish!

## 💡 Inspiration

Locopilot is inspired by Copilot, Claude Code, Dev-GPT, OpenDevin, and the emerging open-source agentic ecosystem—aiming to empower developers with private, supercharged, customizable AI tools.

## 🚦 Quickstart

```bash
# Install from PyPI
pip install locopilot

# Initialize in your project
locopilot init

# ... then just type your coding tasks and manage the session with slash commands!
```

**Links:**
- [PyPI Package](https://pypi.org/project/locopilot/)
- [GitHub Repository](https://github.com/Ripan-Roy/locopilot-ai)