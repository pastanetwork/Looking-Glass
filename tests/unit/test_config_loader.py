from __future__ import annotations

import copy

from modules.utility.config_loader import (
    DEFAULTS,
    _clamp_limits,
    _deep_merge,
    _env_bool,
    _env_int,
    _resolve_ip_hash_salt,
)


class TestDeepMerge:
    def test_merges_nested_dicts(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}

    def test_override_replaces_scalars(self):
        assert _deep_merge({"k": 1}, {"k": 2}) == {"k": 2}

    def test_does_not_mutate_base(self):
        base = {"a": {"x": 1}}
        _deep_merge(base, {"a": {"x": 9}})
        assert base == {"a": {"x": 1}}


class TestEnvHelpers:
    def test_env_bool_true_values(self, monkeypatch):
        for value in ("1", "true", "True", "YES", "on"):
            monkeypatch.setenv("LG_TEST_FLAG", value)
            assert _env_bool("LG_TEST_FLAG", False) is True

    def test_env_bool_false_and_default(self, monkeypatch):
        monkeypatch.setenv("LG_TEST_FLAG", "nope")
        assert _env_bool("LG_TEST_FLAG", True) is False
        monkeypatch.delenv("LG_TEST_FLAG", raising=False)
        assert _env_bool("LG_TEST_FLAG", True) is True

    def test_env_int(self, monkeypatch):
        monkeypatch.setenv("LG_TEST_INT", "42")
        assert _env_int("LG_TEST_INT", 7) == 42
        monkeypatch.setenv("LG_TEST_INT", "pasunentier")
        assert _env_int("LG_TEST_INT", 7) == 7


class TestClampLimits:
    def test_clamps_excessive_values_to_ceiling(self):
        config = copy.deepcopy(DEFAULTS)
        config["limits"]["ping"]["timeout_seconds"] = 9999
        config["limits"]["ping"]["max_bytes"] = 99999999
        _clamp_limits(config)
        # HARD_CEILINGS ping : timeout 60, max_bytes 65536.
        assert config["limits"]["ping"]["timeout_seconds"] == 60
        assert config["limits"]["ping"]["max_bytes"] == 65536

    def test_keeps_values_below_ceiling(self):
        config = copy.deepcopy(DEFAULTS)
        config["limits"]["ping"]["count"] = 5
        _clamp_limits(config)
        assert config["limits"]["ping"]["count"] == 5


class TestIpHashSalt:
    def test_env_salt_takes_precedence(self, monkeypatch, tmp_path):
        monkeypatch.setenv("IP_HASH_SALT", "sel-explicite")
        assert _resolve_ip_hash_salt(str(tmp_path / "db.sqlite")) == "sel-explicite"

    def test_generated_then_persisted(self, monkeypatch, tmp_path):
        monkeypatch.delenv("IP_HASH_SALT", raising=False)
        db_path = str(tmp_path / "db.sqlite")
        first = _resolve_ip_hash_salt(db_path)
        second = _resolve_ip_hash_salt(db_path)
        assert first and first == second
        assert (tmp_path / ".ip_hash_salt").is_file()
