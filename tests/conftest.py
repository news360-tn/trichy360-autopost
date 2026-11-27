"""owner 27 Nov: the tests must never write the real poster/posting_errors.json (the posting job commits it). Every error note a test
makes goes to a temporary file instead."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "poster"))

import errnote  # noqa: E402

errnote.FILE = Path(tempfile.mkdtemp()) / "posting_errors.json"
