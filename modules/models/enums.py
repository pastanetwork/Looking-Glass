from __future__ import annotations

from enum import Enum


class CommandType(str, Enum):
    PING = "ping"
    TRACEROUTE = "traceroute"
    MTR = "mtr"
    DNS = "dns"


class DnsMode(str, Enum):
    RECORDS = "records"
    TRACE = "trace"


class DnsRecordType(str, Enum):
    ALL = "ALL"
    A = "A"
    AAAA = "AAAA"
    MX = "MX"
    NS = "NS"
    TXT = "TXT"
    CNAME = "CNAME"
    SOA = "SOA"
    CAA = "CAA"
    HTTPS = "HTTPS"
    SRV = "SRV"
    NAPTR = "NAPTR"
    DS = "DS"
    DNSKEY = "DNSKEY"
    TLSA = "TLSA"
    SSHFP = "SSHFP"


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
