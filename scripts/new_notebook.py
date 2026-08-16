"""Interactively scaffold a new notebook in data/ or geocoding/.

Run via `make notebook` (which registers the project's Jupyter kernel first).
Creates a blank notebook with a title cell, wired to that kernel, and does
not launch any server -- open the file in your editor / Jupyter frontend
afterwards.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parent.parent
FOLDER_CHOICES = {
    "1": "data",
    "2": "geocoding",
    "data": "data",
    "geocoding": "geocoding",
}
KERNEL_NAME = os.environ.get("KERNEL_NAME", "geocoding-tool")
KERNEL_DISPLAY = os.environ.get("KERNEL_DISPLAY", "geocoding-tool (.venv)")

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]+")


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        print("\nNo input available -- aborting.")
        sys.exit(1)


def choose_folder() -> Path:
    while True:
        choice = ask("Create notebook in [1] data  or  [2] geocoding? ").casefold()
        folder = FOLDER_CHOICES.get(choice)
        if folder:
            return ROOT / folder
        print("Please enter 1, 2, 'data' or 'geocoding'.")


def choose_name() -> str:
    while True:
        raw = ask("Notebook name (without .ipynb): ")
        if not raw:
            print("Name cannot be empty.")
            continue
        stem = raw[: -len(".ipynb")] if raw.endswith(".ipynb") else raw
        name = _UNSAFE_CHARS.sub("_", stem.strip().replace(" ", "_")).strip("_")
        if not name:
            print("That name has no usable characters -- try letters, numbers, - or _.")
            continue
        return name


def build_notebook(title: str) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata.kernelspec = {
        "display_name": KERNEL_DISPLAY,
        "language": "python",
        "name": KERNEL_NAME,
    }
    nb.metadata.language_info = {"name": "python"}
    nb.cells = [nbformat.v4.new_markdown_cell(f"# {title}")]
    nbformat.validator.normalize(nb)
    return nb


def main() -> None:
    folder = choose_folder()
    name = choose_name()
    path = folder / f"{name}.ipynb"

    if path.exists():
        confirm = ask(f"{path.relative_to(ROOT)} already exists -- overwrite? [y/N] ")
        if confirm.casefold() != "y":
            print("Aborted.")
            sys.exit(1)

    title = name.replace("_", " ").replace("-", " ").strip().title() or name
    nb = build_notebook(title)
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, path)

    print(f"\nCreated {path.relative_to(ROOT)}")
    print(f"Kernel: {KERNEL_DISPLAY} ({KERNEL_NAME}) -- already registered.")
    print("Open it in your editor / Jupyter frontend and select that kernel")
    print("if it isn't picked up automatically.")


if __name__ == "__main__":
    main()
