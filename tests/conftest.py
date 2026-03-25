import tempfile
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DATA_ROOT = ROOT / ".pytest_localappdata"
TEST_DATA_ROOT.mkdir(exist_ok=True)
(TEST_DATA_ROOT / "pytest-temp").mkdir(parents=True, exist_ok=True)
(TEST_DATA_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("LOCALAPPDATA", str(TEST_DATA_ROOT))
os.environ.setdefault("APPDATA", str(TEST_DATA_ROOT))
os.environ.setdefault("TMP", str(TEST_DATA_ROOT))
os.environ.setdefault("TEMP", str(TEST_DATA_ROOT))
os.environ.setdefault("TMPDIR", str(TEST_DATA_ROOT))
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(TEST_DATA_ROOT / "pytest-temp"))
tempfile.tempdir = str(TEST_DATA_ROOT / "tmp")
