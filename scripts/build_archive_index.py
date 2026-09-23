"""Build archive/index.html. Thin wrapper; the logic lives in radar/archive.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar.archive import main  # noqa: E402

if __name__ == "__main__":
    main()
