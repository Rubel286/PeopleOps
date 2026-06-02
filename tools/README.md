# Developer Utilities & Tools

This directory contains standalone helper scripts for developer productivity. These tools are excluded from the main repository distribution using `.gitignore` as per user preferences, but are retained here for active local development.

## Available Tools

### 1. Code Dumper (`codedump.py`)
Generates a complete consolidated `.txt` file containing the source code (`.py`, `.html`, `.css`) of the entire project while filtering out media, caches, databases, virtual environments, and other binary blobs.
- **Run command (from project root):**
  ```bash
  python tools/codedump.py
  ```
- **Output:** `Mainframe_code_dump_COMPLETE.txt` in the project root.

### 2. Directory Tree Printer (`tree.py`)
Prints a beautifully formatted directory tree of the project structure while automatically excluding heavy or irrelevant directories (such as virtual environments, cache folders, upload directories, and node modules).
- **Run command (from project root):**
  ```bash
  python tools/tree.py
  ```

### 3. Resume Extraction Tester (`test_resume_extraction.py`)
Runs extraction and evaluation on PDF resumes found within the root `resumes/` folder using our NLP service and PyMuPDF logic, outputting detailed intelligence reports for quick testing.
- **Run command (from project root):**
  ```bash
  python tools/test_resume_extraction.py
  ```
