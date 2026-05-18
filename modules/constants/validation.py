from __future__ import annotations

import re

MAX_TARGET_LENGTH = 255
MAX_NODE_ID_LENGTH = 64

HOSTNAME_REGEX = re.compile(
    r"^(?=.{1,253}\.?$)"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.?$"
)
