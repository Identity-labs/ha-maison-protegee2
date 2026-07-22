"""Make the repo-root maison_protegee package importable from Home Assistant."""

from __future__ import annotations

import sys
from pathlib import Path


def setup_import_path() -> None:
    """Prefer the bundled lib/, then repo root, then an already-installed package."""
    component_dir = Path(__file__).resolve().parent
    for root in (component_dir / "lib", component_dir.parent.parent):
        if (root / "maison_protegee" / "client.py").is_file():
            root_str = str(root)
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
            return

    try:
        import maison_protegee

        package_dir = Path(maison_protegee.__file__).resolve().parent
        if (package_dir / "client.py").is_file():
            return
    except ImportError:
        pass

    raise ImportError(
        "maison_protegee package not found. Expected "
        "custom_components/maison_protegee/lib/maison_protegee/ "
        "(run scripts/sync_ha_lib.sh), or install with "
        "'pip install -e .' from the ha-maison-protegee2 repo root."
    )
