from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from modules.constants.validation import MAX_NODE_ID_LENGTH, MAX_TARGET_LENGTH
from modules.models.enums import CommandType, DnsMode, DnsRecordType, IpFamily


class SecureBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CommandRequest(SecureBaseModel):
    node_id: str = Field(min_length=1, max_length=MAX_NODE_ID_LENGTH)
    tool: CommandType
    target: str = Field(min_length=1, max_length=MAX_TARGET_LENGTH)
    family: IpFamily = IpFamily.AUTO
    turnstile_token: str = Field(default="", max_length=4096)
    dns_mode: DnsMode = DnsMode.RECORDS
    dns_record: DnsRecordType = DnsRecordType.ALL
