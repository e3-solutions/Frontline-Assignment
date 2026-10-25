from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_AGENT = ROOT / "voice-agent"
SHARED = ROOT / "shared"
for directory in (str(VOICE_AGENT), str(SHARED)):
    if directory not in sys.path:
        sys.path.insert(0, directory)
