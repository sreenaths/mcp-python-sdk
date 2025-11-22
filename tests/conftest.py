import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--use-existing-minimcp-server",
        action="store_true",
        default=False,
        help="Use an already running MinimCP server if available.",
    )
