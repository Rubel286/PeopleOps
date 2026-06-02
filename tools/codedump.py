import os

OUTPUT_FILE = "../Peopleops_code_dump_COMPLETE.txt"

EXCLUDE_DIRS = {
    ".git", ".vs", "__pycache__", "venv", "env", "node_modules",
    "models", "checkpoints", "migrations", "logs", ".idea",
    "mail_output", "uploads", "venv_enterprise"
}

EXCLUDE_FILES = {
    ".gitignore", "project_code_dump.txt", "codedump.py"
}

EXCLUDE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
    ".db", ".sqlite", ".exe", ".dll", ".zip", ".tar", ".gz",
    ".pyc", ".pyo", ".so", ".vsidx", ".wsuo", ".json",
    ".csv", ".sav", ".pkl", ".h5"
}


def should_exclude_file(path: str) -> bool:
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()

    if name in EXCLUDE_FILES:
        return True

    if ext in EXCLUDE_EXTS:
        return True

    return False


def dump_files(root_dir: str):

    # Adjust path if running from inside the tools/ folder
    output_path = os.path.join(root_dir, "Peopleops_code_dump_COMPLETE.txt")

    with open(output_path, "w", encoding="utf-8", errors="ignore") as out:

        for dirpath, dirnames, filenames in os.walk(root_dir):

            # CRITICAL: prevent recursion into excluded dirs
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

            for filename in filenames:

                if should_exclude_file(filename):
                    continue

                if not filename.endswith((".py", ".html", ".css")):
                    continue

                abs_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(abs_path, root_dir)

                # STRONG FILE START MARKER
                out.write("\n")
                out.write("=" * 80 + "\n")
                out.write(f"FILE_START: {rel_path}\n")
                out.write("=" * 80 + "\n\n")

                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        out.write(content)

                except Exception as e:
                    out.write(f"\nERROR_READING_FILE: {e}\n")

                # STRONG FILE END MARKER
                out.write("\n\n")
                out.write("=" * 80 + "\n")
                out.write(f"FILE_END: {rel_path}\n")
                out.write("=" * 80 + "\n\n")

    print(f"\nCOMPLETE dump written to: {output_path}")


if __name__ == "__main__":
    # Dump from the parent project root directory
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dump_files(parent_dir)
