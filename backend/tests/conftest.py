import os
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Runs at collection time, before any test module imports app.main (which
# creates the control-plane async engine at import time from whatever
# CONTROL_PLANE_DB_URL is set right now). A dedicated, freshly-wiped temp
# file keeps auth/workspace tests isolated from anything left on disk by a
# previous run (fixed test emails would otherwise collide on a second run),
# without needing a real Postgres in CI.
_TEST_CONTROL_PLANE_DB = Path(tempfile.gettempdir()) / "ai_sql_studio_test_control_plane.db"
if "CONTROL_PLANE_DB_URL" not in os.environ:
    _TEST_CONTROL_PLANE_DB.unlink(missing_ok=True)
    os.environ["CONTROL_PLANE_DB_URL"] = f"sqlite+aiosqlite:///{_TEST_CONTROL_PLANE_DB}"
