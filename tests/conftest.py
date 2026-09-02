"""flux's tests import black-oxide's rustc adapter for the build/run judge
(the reuse contract, spec §5). Put both roots on sys.path without
depending on how pytest was launched."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OXIDE = Path.home() / "workspace" / "oxide"
for p in (str(ROOT), str(OXIDE)):
    if p not in sys.path:
        sys.path.insert(0, p)
