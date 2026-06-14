"""Tiny notebook builder so hour content reads as prose, not JSON.

Cells are specified as a list of 2-tuples:
    [("md", "# Title\n\nSome markdown."), ("code", "print(1+1)"), ...]

Usage:
    from scripts._nb import write_notebook
    write_notebook("notebooks/hour00_setup.ipynb", [...])

The resulting file is a valid Jupyter notebook v4. It opens in JupyterLab,
VSCode, or any Jupyter-compatible viewer with zero conversion.

Every notebook gets a BOOTSTRAP cell at the very top that adds the project
root to sys.path. This means the notebook works whether the user launches
Jupyter from the project root or from notebooks/, with or without
`pip install -e .`. It's a small redundancy that removes a class of
beginner-friction errors.
"""

from __future__ import annotations

import json
from pathlib import Path

Cell = tuple[str, str]  # ("md" | "code", content)

BOOTSTRAP = """\
# --- bootstrap: make `kg_tutorial` importable regardless of cwd ---
import sys
from pathlib import Path
_here = Path.cwd()
_root = _here if (_here / "kg_tutorial").exists() else _here.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
# -----------------------------------------------------------------
"""


def _mk_md(src: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": src.splitlines(keepends=True) if src else [],
    }


def _mk_code(src: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src.splitlines(keepends=True) if src else [],
    }


def write_notebook(path: str | Path, cells: list[Cell], *, kernel: str = "python3") -> Path:
    # Prepend the bootstrap as the first code cell of every notebook
    cells_with_bootstrap: list[Cell] = [("code", BOOTSTRAP)] + cells
    nb = {
        "cells": [_mk_md(c) if k == "md" else _mk_code(c) for k, c in cells_with_bootstrap],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": kernel,
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(nb, indent=1))
    return p
