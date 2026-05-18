from __future__ import annotations

import logging
import sys

import pytest

from modules.executors.commands import build_command_spec
from modules.executors.local import LocalCommandStream
from modules.models.enums import CommandStatus, CommandType
from modules.utility.system import IS_WINDOWS

LIMITS = {
    "ping": {"count": 5, "timeout_seconds": 12, "max_lines": 40, "max_bytes": 8192},
    "traceroute": {"max_hops": 20, "timeout_seconds": 30, "max_lines": 80, "max_bytes": 16384},
    "mtr": {"report_cycles": 5, "timeout_seconds": 30, "max_lines": 80, "max_bytes": 16384},
}
_SHELL_METACHARS = (";", "|", "&", "$", "`", ">", "<", "\n", "(", ")", "*", "?")
_IS_WINDOWS = IS_WINDOWS


class TestCommandSpecs:
    def test_builds_each_tool(self):
        for ct in CommandType:
            spec = build_command_spec(ct, LIMITS[ct.value])
            assert spec.command_type == ct

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError):
            build_command_spec("nmap", LIMITS["ping"])

    def test_limits_applied(self):
        spec = build_command_spec(CommandType.PING, LIMITS["ping"])
        assert spec.timeout_seconds == 12
        assert spec.max_lines == 40
        assert spec.max_bytes == 8192

    @pytest.mark.parametrize("ct", list(CommandType))
    def test_argv_is_list_of_str(self, ct):
        argv = build_command_spec(ct, LIMITS[ct.value]).build_argv("8.8.8.8", 4)
        assert isinstance(argv, list)
        assert argv and all(isinstance(a, str) for a in argv)

    @pytest.mark.parametrize("ct", list(CommandType))
    def test_argv_ends_with_target(self, ct):
        argv = build_command_spec(ct, LIMITS[ct.value]).build_argv("2001:4860:4860::8888", 6)
        assert argv[-1] == "2001:4860:4860::8888"

    @pytest.mark.parametrize("ct", list(CommandType))
    def test_argv_has_no_shell_metacharacters(self, ct):
        argv = build_command_spec(ct, LIMITS[ct.value]).build_argv("8.8.8.8", 4)
        joined = " ".join(argv)
        for meta in _SHELL_METACHARS:
            assert meta not in joined

    @pytest.mark.skipif(_IS_WINDOWS, reason="forme POSIX uniquement")
    def test_posix_argv_terminates_options(self):
        for ct in CommandType:
            argv = build_command_spec(ct, LIMITS[ct.value]).build_argv("8.8.8.8", 4)
            assert "--" in argv
            assert argv.index("--") == len(argv) - 2


class TestLocalCommandStream:
    async def test_streams_lines_and_completes(self):
        spec = build_command_spec(CommandType.PING, LIMITS["ping"])
        argv = [sys.executable, "-c", "print('alpha'); print('beta')"]
        stream = LocalCommandStream(argv, spec, logging.getLogger("test"))
        lines = [line async for line in stream]
        assert "alpha" in lines and "beta" in lines
        assert stream.status == CommandStatus.OK
        assert stream.exit_code == 0
        assert stream.duration_ms is not None

    async def test_missing_binary_ends_in_error(self):
        spec = build_command_spec(CommandType.PING, LIMITS["ping"])
        stream = LocalCommandStream(["binaire-inexistant-xyz-123"], spec, logging.getLogger("test"))
        lines = [line async for line in stream]
        assert lines == []
        assert stream.status == CommandStatus.ERROR

    async def test_max_lines_kills_stream(self):
        spec = build_command_spec(CommandType.PING, {**LIMITS["ping"], "max_lines": 3})
        argv = [sys.executable, "-c", "import sys\n[print(i) or sys.stdout.flush() for i in range(50)]"]
        stream = LocalCommandStream(argv, spec, logging.getLogger("test"))
        lines = [line async for line in stream]
        assert len(lines) <= 4
        assert stream.status == CommandStatus.KILLED
