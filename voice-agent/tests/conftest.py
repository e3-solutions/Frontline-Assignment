"""Import paths and isolated defaults for the functional tests."""

import os
import sys
from pathlib import Path

_VOICE_AGENT_ROOT = Path(__file__).parent.parent.resolve()
if str(_VOICE_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_VOICE_AGENT_ROOT))

os.environ.setdefault("SUPABASE_URL", "http://test-suite.local")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
