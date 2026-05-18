from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from pydantic import ValidationError

from modules.constants.validation import MAX_TARGET_LENGTH
from modules.executors.commands import build_command_spec
from modules.models.enums import CommandStatus
from modules.models.schemas import CommandRequest
from modules.utility.hashing import hash_ip
from modules.utility.ip_validation import validate_target

if TYPE_CHECKING:
    import logging

    from modules.executors.base import NodeExecutor
    from modules.executors.commands.base import CommandSpec
    from modules.executors.registry import NodeRegistry
    from modules.repositories.query_log_repo import QueryLogRepository
    from modules.services.concurrency_service import ConcurrencyService
    from modules.services.turnstile_service import TurnstileService


@dataclass
class PrepareResult:
    ok: bool
    http: int = 200
    error: Optional[str] = None
    executor: Optional[NodeExecutor] = None
    spec: Optional[CommandSpec] = None
    ip: Optional[str] = None
    family: Optional[int] = None
    display: Optional[str] = None
    node_id: Optional[str] = None
    command_type: Optional[str] = None
    ip_hash: Optional[str] = None


class CommandService:
    def __init__(
        self,
        config: dict,
        registry: NodeRegistry,
        concurrency: ConcurrencyService,
        turnstile: TurnstileService,
        query_log: QueryLogRepository,
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._registry = registry
        self._concurrency = concurrency
        self._turnstile = turnstile
        self._query_log = query_log
        self._logger = logger
        self._salt = config["ip_hash_salt"]
        self._targets_cfg = config["targets"]
        self._limits = config["limits"]

    def hash_ip(self, ip: str) -> str:
        """
        Hache une IP source avec le sel de configuration.

        Parameters:
            ip (str): adresse IP du client.

        Returns:
            str: empreinte hexadécimale SHA-256 de l'IP.
        """
        return hash_ip(ip, self._salt)

    async def prepare(self, payload: dict, client_ip: str) -> PrepareResult:
        """
        Valide une requête et réserve un slot de concurrence.

        Parameters:
            payload (dict): corps brut de la requête HTTP.
            client_ip (str): adresse IP du client.

        Returns:
            PrepareResult: ticket d'exécution (ok=True) ou descriptif d'erreur (ok=False).
        """
        ip_hash = self.hash_ip(client_ip)

        try:
            req = CommandRequest.model_validate(payload)
        except ValidationError:
            return PrepareResult(ok=False, http=400, error="err_generic")

        node_id, tool, target = req.node_id, req.tool.value, req.target

        executor = self._registry.get(node_id)
        if executor is None or tool not in executor.tools:
            await self._record_rejected(node_id, tool, target, ip_hash)
            return PrepareResult(ok=False, http=400, error="err_generic")

        validated = await validate_target(target, req.family, self._targets_cfg)
        if not validated.ok:
            await self._record_rejected(node_id, tool, target, ip_hash)
            return PrepareResult(ok=False, http=422, error=validated.error or "err_target")

        if not await self._turnstile.verify(req.turnstile_token, client_ip):
            await self._record_rejected(node_id, tool, target, ip_hash)
            return PrepareResult(ok=False, http=403, error="err_turnstile")

        acquired = await self._concurrency.acquire(ip_hash)
        if not acquired.ok:
            await self._record_rejected(node_id, tool, target, ip_hash)
            return PrepareResult(ok=False, http=acquired.http, error=acquired.error)

        try:
            spec = build_command_spec(req.tool, self._limits[tool])
        except Exception:
            await self._concurrency.release(ip_hash)
            self._logger.exception("Construction de la spécification de commande échouée")
            return PrepareResult(ok=False, http=500, error="err_generic")

        return PrepareResult(
            ok=True,
            executor=executor,
            spec=spec,
            ip=validated.ip,
            family=validated.family,
            display=validated.display,
            node_id=node_id,
            command_type=tool,
            ip_hash=ip_hash
        )

    async def finalize(
        self, ticket: PrepareResult, status: CommandStatus,
        exit_code: Optional[int], duration_ms: Optional[int],
    ) -> None:
        """
        Libère le slot de concurrence et écrit l'entrée de journal.

        Parameters:
            ticket (PrepareResult): ticket émis par prepare().
            status (CommandStatus): statut final de l'exécution (ok, timeout, error, killed).
            exit_code (Optional[int]): code de retour du processus, ou None.
            duration_ms (Optional[int]): durée d'exécution en millisecondes, ou None.
        """
        if ticket.ip_hash:
            await self._concurrency.release(ticket.ip_hash)

        await self._query_log.create(
            node_id=ticket.node_id or "?",
            command_type=ticket.command_type or "?",
            target=ticket.display or ticket.ip or "?",
            family=ticket.family,
            source_ip_hash=ticket.ip_hash or "",
            status=status.value,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )

    async def _record_rejected(self, node_id: str, tool: str, target: str, ip_hash: str) -> None:
        """
        Journalise une requête rejetée pour la visibilité des tentatives d'abus.

        Parameters:
            node_id (str): identifiant du nœud cible.
            tool (str): outil demandé (ping, traceroute, mtr).
            target (str): cible brute indiquée dans la requête.
            ip_hash (str): empreinte hachée de l'IP source.
        """
        await self._query_log.create(
            node_id=node_id,
            command_type=tool,
            target=target[:MAX_TARGET_LENGTH],
            family=None,
            source_ip_hash=ip_hash,
            status=CommandStatus.REJECTED.value,
            exit_code=None,
            duration_ms=None,
        )
