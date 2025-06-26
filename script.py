import os

project_structure = {
    "locopilot": {
        "locopilot": [
            "__init__.py",
            "cli.py",
            "agent.py",
            "memory.py",
            "utils.py",
            "connection.py"
        ],
        "tests": [
            "test_basic.py"
        ],
        "root_files": [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            ".gitignore"
        ]
    }
}

def make_structure(base, structure):
    os.makedirs(base, exist_ok=True)
    for folder, contents in structure.items():
        folder_path = os.path.join(base, folder)
        if isinstance(contents, list):  # For files in the folder
            os.makedirs(folder_path, exist_ok=True)
            for file in contents:
                open(os.path.join(folder_path, file), 'a').close()
        elif isinstance(contents, dict):
            make_structure(folder_path, contents)
        elif folder == "root_files":
            for file in contents:
                open(os.path.join(base, file), 'a').close()

# Actually create the structure
base_dir = "locopilot"
os.makedirs(base_dir, exist_ok=True)

# Create inner folders and files
make_structure(base_dir, {
    "locopilot": [
        "__init__.py", "cli.py", "agent.py", "memory.py", "utils.py", "connection.py"
    ],
    "tests": [
        "test_basic.py"
    ],
    "root_files": [
        "pyproject.toml", "README.md", "LICENSE", ".gitignore"
    ]
})

print("✅ Project structure created successfully!")
