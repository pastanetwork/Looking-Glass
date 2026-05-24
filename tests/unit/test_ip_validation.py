from __future__ import annotations

from ipaddress import ip_address

import pytest

from modules.constants.validation import HOSTNAME_REGEX
from modules.models.enums import IpFamily
from modules.utility.ip_validation import check_ip, validate_dns_target, validate_target

DEFAULT_CFG = {
    "block_private": True,
    "block_bogon": True,
    "allow_list": [],
    "block_list": [],
    "allow_hostnames": True,
    "max_hostname_length": 253,
}


# ===================== Regex de nom d'hôte =====================

class TestHostnameRegex:
    @pytest.mark.parametrize("host", [
        "example.com", "a.b.c.d.example.org", "sub-domain.example.com",
        "xn--bcher-kva.example", "EXAMPLE.COM", "n1.host.net",
    ])
    def test_accepts_valid_hostnames(self, host):
        assert HOSTNAME_REGEX.match(host)

    @pytest.mark.parametrize("payload", [
        "8.8.8.8; rm -rf /", "host && id", "host | nc evil 1", "$(reboot)",
        "`id`", "host\nid", "a b", "host;ls", "-rf", "host/../etc",
        "host'", 'host"', "host>file", "host<file", "host*", "héte.com",
    ])
    def test_rejects_injection_payloads(self, payload):
        assert not HOSTNAME_REGEX.match(payload)

    def test_rejects_leading_trailing_hyphen(self):
        assert not HOSTNAME_REGEX.match("-host.com")
        assert not HOSTNAME_REGEX.match("host-.com")


# ===================== check_ip =====================

class TestCheckIp:
    @pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "9.9.9.9", "2001:4860:4860::8888"])
    def test_public_ip_allowed(self, ip):
        assert check_ip(ip_address(ip), DEFAULT_CFG) is None

    @pytest.mark.parametrize("ip", [
        "10.0.0.1", "192.168.1.1", "172.16.5.5", "127.0.0.1", "169.254.0.1",
        "0.0.0.0", "224.0.0.1", "192.0.2.10", "198.51.100.1", "203.0.113.1",
        "100.64.0.1", "255.255.255.255", "::1", "fe80::1", "2001:db8::1", "fc00::1",
    ])
    def test_special_ip_rejected(self, ip):
        assert check_ip(ip_address(ip), DEFAULT_CFG) == "err_target"

    def test_block_list_rejects(self):
        cfg = {**DEFAULT_CFG, "block_list": ["8.8.8.0/24"]}
        assert check_ip(ip_address("8.8.8.8"), cfg) == "err_target"

    def test_allow_list_restricts(self):
        cfg = {**DEFAULT_CFG, "allow_list": ["1.1.1.0/24"]}
        assert check_ip(ip_address("1.1.1.1"), cfg) is None
        assert check_ip(ip_address("8.8.8.8"), cfg) == "err_target"

    def test_private_allowed_when_block_disabled(self):
        cfg = {**DEFAULT_CFG, "block_private": False, "block_bogon": False}
        assert check_ip(ip_address("10.0.0.1"), cfg) is None
        # Multicast reste toujours bloqué.
        assert check_ip(ip_address("224.0.0.1"), cfg) == "err_target"


# ===================== validate_target =====================

class TestValidateTarget:
    async def test_public_ipv4_ok(self):
        result = await validate_target("8.8.8.8", IpFamily.AUTO, DEFAULT_CFG)
        assert result.ok and result.ip == "8.8.8.8" and result.family == 4

    async def test_public_ipv6_ok(self):
        result = await validate_target("2001:4860:4860::8888", IpFamily.AUTO, DEFAULT_CFG)
        assert result.ok and result.family == 6

    async def test_private_ip_rejected(self):
        result = await validate_target("192.168.1.1", IpFamily.AUTO, DEFAULT_CFG)
        assert not result.ok and result.error == "err_target"

    async def test_family_mismatch_rejected(self):
        result = await validate_target("8.8.8.8", IpFamily.V6, DEFAULT_CFG)
        assert not result.ok

    @pytest.mark.parametrize("payload", [
        "8.8.8.8; id", "$(reboot)", "`whoami`", "a|b", "host && ls", "8.8.8.8 -oG",
    ])
    async def test_injection_payload_rejected(self, payload):
        result = await validate_target(payload, IpFamily.AUTO, DEFAULT_CFG)
        assert not result.ok

    async def test_localhost_hostname_rejected(self):
        # localhost résout vers une adresse loopback (défense DNS-rebinding).
        result = await validate_target("localhost", IpFamily.AUTO, DEFAULT_CFG)
        assert not result.ok

    async def test_hostnames_disabled(self):
        cfg = {**DEFAULT_CFG, "allow_hostnames": False}
        result = await validate_target("example.com", IpFamily.AUTO, cfg)
        assert not result.ok

    async def test_empty_and_too_long_rejected(self):
        assert not (await validate_target("", IpFamily.AUTO, DEFAULT_CFG)).ok
        assert not (await validate_target("a" * 300, IpFamily.AUTO, DEFAULT_CFG)).ok


# ===================== validate_dns_target =====================

class TestValidateDnsTarget:
    async def test_hostname_passes_without_resolution(self):
        result = await validate_dns_target("example.com", DEFAULT_CFG)
        assert result.ok and result.ip == "example.com" and result.family == 0

    async def test_literal_public_ip_passes(self):
        result = await validate_dns_target("8.8.8.8", DEFAULT_CFG)
        assert result.ok and result.ip == "8.8.8.8" and result.family == 4

    async def test_literal_private_ip_rejected(self):
        result = await validate_dns_target("192.168.1.1", DEFAULT_CFG)
        assert not result.ok and result.error == "err_target"

    async def test_injection_payload_rejected(self):
        result = await validate_dns_target("example.com; id", DEFAULT_CFG)
        assert not result.ok

    async def test_trace_resolves_and_rejects_loopback(self):
        # En mode trace, localhost doit être refusé même comme nom d'hôte (SSRF DNS).
        result = await validate_dns_target("localhost", DEFAULT_CFG, require_public_ip=True)
        assert not result.ok and result.error == "err_target"

    async def test_trace_accepts_public_hostname(self):
        result = await validate_dns_target("example.com", DEFAULT_CFG, require_public_ip=True)
        assert result.ok and result.ip == "example.com"
