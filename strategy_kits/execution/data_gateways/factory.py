from typing import Literal

from .base import BaseDataGateway
from .jq_gateway import JQDataGateway


def create_gateway(kind: Literal["jq"], **kwargs) -> BaseDataGateway:
    if kind == "jq":
        return JQDataGateway(**kwargs)
    else:
        raise ValueError(f"Unknown gateway kind: {kind}")