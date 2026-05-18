from __future__ import annotations

from ipaddress import ip_address

from modules.executors.commands.base import CommandSpec
from modules.models.enums import CommandType, DnsMode, DnsRecordType
from modules.utility.ip_validation import redact_internal_ips
from modules.utility.system import IS_WINDOWS

_RECORDS_ALL = (
    "A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA", "HTTPS",
    "SRV", "NAPTR", "DS", "DNSKEY", "TLSA", "SSHFP",
)
_RECORD_VALUES = frozenset(t.value for t in DnsRecordType)


class DigCommand(CommandSpec):
    command_type = CommandType.DNS
    target_kind = "hostname"

    def __init__(self, limits: dict) -> None:
        super().__init__(limits)
        self.mode: str = DnsMode.RECORDS.value
        self.record: str = DnsRecordType.ALL.value

    def bind_options(self, options: dict) -> None:
        """
        Applique le mode d'interrogation et le type d'enregistrement demandés.

        Parameters:
            options (dict): options de requête (dns_mode, dns_record).
        """
        mode = options.get("dns_mode")
        record = options.get("dns_record")
        if mode in (DnsMode.TRACE.value, DnsMode.RECORDS.value):
            self.mode = mode
        if record in _RECORD_VALUES:
            self.record = record

    def binary(self) -> str:
        """
        Retourne le nom du binaire dig.

        Returns:
            str: "dig".
        """
        return "dig"

    def build_argv(self, ip: str, family: int) -> list[str]:
        """
        Construit l'argv de la commande dig pour la cible donnée.

        Parameters:
            ip (str): nom d'hôte validé, ou IP littérale (recherche inverse PTR).
            family (int): famille de transport (4, 6, ou 0 pour automatique).

        Returns:
            list[str]: argv prêt à être passé à asyncio.create_subprocess_exec.
        """
        is_trace = self.mode == DnsMode.TRACE.value
        args: list[str] = ["dig", "+nocmd", "+timeout=2", "+tries=1"]

        if family == 4:
            args.append("-4")
        elif family == 6:
            args.append("-6")

        if is_trace:
            args.append("+trace")
        else:
            args += ["+noall", "+comments", "+answer"]

        if self._is_ip(ip):
            args += ["-x", ip]
        elif is_trace:
            args += [ip, self._trace_record()]
        elif self.record == DnsRecordType.ALL.value:
            for rtype in _RECORDS_ALL:
                args += [ip, rtype]
        else:
            args += [ip, self.record]

        if IS_WINDOWS:
            return args

        return ["stdbuf", "-oL", *args]

    def filter_line(self, line: str) -> str:
        """Masque les IP internes éventuellement présentes dans les réponses DNS."""
        return redact_internal_ips(line)

    def _trace_record(self) -> str:
        """
        Retourne le type d'enregistrement à tracer.

        Returns:
            str: le type choisi, ou "A" si « Tous » est sélectionné (incompatible avec +trace).
        """
        if self.record == DnsRecordType.ALL.value:
            return DnsRecordType.A.value

        return self.record

    @staticmethod
    def _is_ip(value: str) -> bool:
        """
        Indique si la chaîne est une IP littérale (déclenche une recherche inverse).

        Parameters:
            value (str): cible à tester.

        Returns:
            bool: True si la chaîne est une adresse IP valide.
        """
        try:
            ip_address(value)
        except ValueError:
            return False

        return True
