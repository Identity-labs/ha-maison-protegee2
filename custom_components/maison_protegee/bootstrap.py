"""Make the repo-root maison_protegee package importable from Home Assistant."""

from __future__ import annotations

import sys
from pathlib import Path


def setup_import_path() -> None:
    """Add repo root (or bundled lib/) to sys.path if maison_protegee is not installed."""
    try:
        import maison_protegee  # noqa: F401

        return
    except ImportError:
        pass

    component_dir = Path(__file__).resolve().parent
    for root in (component_dir.parent.parent, component_dir / "lib"):
        if (root / "maison_protegee" / "client.py").is_file():
            root_str = str(root)
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
            return

    raise ImportError(
        "maison_protegee package not found. Install with "
        "'pip install -e .' from the ha-maison-protegee2 repo root, "
        "or copy maison_protegee/ into custom_components/maison_protegee/lib/"
    )
