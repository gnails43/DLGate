import re
from typing import Optional

from dlgate.gates.base import BaseGateHandler
from dlgate.gates.hypeddit import HypedditHandler

GATE_HANDLERS: list[tuple[str, type[BaseGateHandler]]] = [
    (r"hypeddit\.com", HypedditHandler),
]


def get_handler(url: str) -> Optional[BaseGateHandler]:
    for pattern, handler_cls in GATE_HANDLERS:
        if re.search(pattern, url):
            return handler_cls()
    return None
