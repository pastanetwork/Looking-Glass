from __future__ import annotations

from enum import Enum


class CommandType(str, Enum):
    PING = "ping"
    TRACEROUTE = "traceroute"
    MTR = "mtr"


class CommandStatus(str, Enum):
    RUNNING = "running"
    OK = "ok"
    TIMEOUT = "timeout"
    ERROR = "error"
    REJECTED = "rejected"
    KILLED = "killed"


class IpFamily(str, Enum):
    AUTO = "auto"
    V4 = "4"
    V6 = "6"
