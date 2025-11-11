from abc import ABC, abstractmethod
from typing import Generic

from mcp.server.minimcp.managers.context_manager import ScopeT
from mcp.server.minimcp.minimcp import MiniMCP
from mcp.server.minimcp.types import Message


class BaseTransport(Generic[ScopeT], ABC):
    """
    Base class for all transport implementations.

    Attributes:
        minimcp: The MiniMCP instance to handle the message dispatched by the transport.
    """

    minimcp: MiniMCP[ScopeT]

    def __init__(self, minimcp: MiniMCP[ScopeT]) -> None:
        self.minimcp = minimcp

    @abstractmethod
    async def dispatch(self, received_msg: Message) -> None:
        """
        Dispatch an incoming message to the MiniMCP instance.

        Args:
            received_msg: The message to dispatch to the MiniMCP instance
        """
        raise NotImplementedError
