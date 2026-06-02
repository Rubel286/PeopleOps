import os
import sys
import io

# --- Fix Windows console encoding for UTF-8 ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Folders/files you want to skip
EXCLUDE = {
    "__pycache__",
    ".git",
    ".idea",
    "node_modules",
    "mail_output",
    "uploads",
    "models",
    "venv_enterprise",
    "enterprise_uploads",
    "enterprise_mail_output",
    "License",
    "tree.py",
    "tools",  # exclude tools itself from recursive tree view if desired
}

def print_tree(path, prefix=""):
    items = sorted([i for i in os.listdir(path) if i not in EXCLUDE])
    pointers = ["├── "] * (len(items) - 1) + ["└── "]

    for pointer, item in zip(pointers, items):
        full_path = os.path.join(path, item)
        print(prefix + pointer + item)

        if os.path.isdir(full_path):
            extension = "│   " if pointer == "├── " else "    "
            print_tree(full_path, prefix + extension)

if __name__ == "__main__":
    # Point to the main project directory by default if running from tools/
    current_dir = os.path.abspath(".")
    if os.path.basename(current_dir) == "tools":
        project_path = os.path.abspath("..")
    else:
        project_path = current_dir

    print(os.path.basename(project_path) + "/")
    print_tree(project_path)
