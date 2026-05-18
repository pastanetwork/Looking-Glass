from __future__ import annotations

import sys

IS_WINDOWS: bool = sys.platform == "win32"

# Windows écrit la sortie des sous-processus dans la page de codes OEM de la
# console ; les autres systèmes émettent en UTF-8.
SUBPROCESS_OUTPUT_ENCODING: str = "oem" if IS_WINDOWS else "utf-8"
