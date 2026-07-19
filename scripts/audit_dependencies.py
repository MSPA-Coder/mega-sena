from __future__ import annotations

import runpy
import sys
from pathlib import Path

import truststore


def main() -> None:
    """Executa pip-audit usando a cadeia de certificados confiada pelo sistema."""
    project_root = Path(__file__).resolve().parents[1]
    truststore.inject_into_ssl()
    sys.argv = [
        "pip-audit",
        "--requirement",
        str(project_root / "requirements.txt"),
        "--progress-spinner",
        "off",
    ]
    runpy.run_module("pip_audit", run_name="__main__")


if __name__ == "__main__":
    main()
