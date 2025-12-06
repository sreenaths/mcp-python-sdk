<div align="center">

<!-- omit in toc -->
# ✨ MiniMCP

A **minimal, stateless, and lightweight** framework for building MCP servers.
</div>

_MiniMCP is designed with simplicity at its core, it exposes a single asynchronous function to handle MCP messages—Pass in a request message, and it returns the response message_ ⭐ _While bidirectional messaging is supported, it’s not a mandatory requirement—So you can use plain HTTP transport for communication_ ⭐ _MiniMCP is primarily built for remote MCP servers but works just as well for local servers_ ⭐ _MiniMCP ships with built-in transport mechanisms (stdio, HTTP, and 'Smart' Streamable HTTP)—You’re free to use them as it is or extend them to suit your needs_ ⭐ _Makes it possible to add MCP inside any Python web application, and use your existing auth mechanisms_ ⭐ _MiniMCP is built on the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), ensuring standardized context and resource sharing._ ⭐ _Hook handlers to a MiniMCP instance, wrap it inside any of the provided transports and your MCP server is ready!_

## Table of Contents

- [What is MCP?](#what-is-mcp)
- [Why MiniMCP?](#why-minimcp)
  - [Currently Supported Features](#currently-supported-features)
  - [Planned Features](#planned-features-if-needed)
  - [Unlikely Features](#unlikely-features)
- [Using MiniMCP](#using-minimcp)
  - [Installation](#installation)
  - [Basic Setup](#basic-setup)
  - [FastAPI Integration](#fastapi-integration)
- [API Reference](#api-reference)
  - [MiniMCP](#minimcp)
  - [Primitive Managers/Decorators](#primitive-managersdecorators)
    - [Tool Manager](#tool-manager)
    - [Prompt Manager](#prompt-manager)
    - [Resource Manager](#resource-manager)
  - [Context Manager](#context-manager)
- [Transports](#transports)
- [Testing](#testing)
- [Error Handling](#error-handling)
- [Examples](#examples)
  - [Claude Desktop](#claude-desktop)

## What is MCP?

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io) is a powerful, standardized way for AI applications to connect with external data sources and tools. It follows a client–server architecture, where communication happens through well-defined MCP messages in the JSON-RPC 2.0 format. The key advantage of MCP is interoperability: once a server supports MCP, any MCP-compatible AI client can connect to it without custom integration code. The official MCP Python SDK provides a low-level implementation of the protocol, while [FastMCP](https://github.com/jlowin/fastmcp) offers a higher-level, Pythonic interface.

## Why MiniMCP?

MiniMCP rethinks the MCP server from the ground up, keeping the core functionality lightweight and independent of transport layer, bidirectional communication, session management, and auth mechanisms. Additionally, instead of a stream-based interface, MiniMCP exposes a simple asynchronous handle function that takes a JSON-RPC 2.0 message string as input and returns a JSON-RPC 2.0 message string as output.

- **Stateless:** Scalability, simplicity, and reliability are crucial for remote MCP servers. MiniMCP provides all of those by being stateless at its core — each request is self-contained, and the server maintains no persistent session state.
  - This design makes it robust and easy to scale horizontally.
  - This also makes it a perfect fit for **serverless architectures**, where ephemeral execution environments are the norm.
  - Want to start your MCP server using uvicorn with multiple workers? No problem.
- **Bidirectional is optional:** Many use cases work perfectly with a simple request–response channel without needing bidirectional communication. MiniMCP was built with this in mind and provides a simple HTTP transport while adhering to the specification.
- **Embeddable:** Already have an application built with FastAPI (or another framework)? You can embed a MiniMCP server under a single endpoint, or multiple servers under multiple endpoints — _As a cherry on the cake, you can use your existing dependency injection system._
- **Scope and Context:** MiniMCP provides a type-checked scope object that travels with each message. This allows you to pass extra details such as authentication, user info, session data, or database handles. Inside the handler, the scope is available as part of the context — _So you’re free to use your preferred session or user management mechanisms._
- **Security:** MiniMCP encourages you to use your existing battle-tested security mechanism instead of enforcing one - _In other words, a MiniMCP server built with FastAPI can be as secure as any FastAPI application!_
- **Stream on Demand:** MiniMCP comes with a smart streamable HTTP transport. It opens an event stream only when the server needs to push notifications to the client.
- **Separation of Concerns:** The transport layer is fully decoupled from message handling. This makes it easy to adapt MiniMCP to different environments and transport protocols without rewriting your core business logic.
- **Minimal Dependencies:** MiniMCP keeps its footprint small, depending only on the official MCP SDK.

### Currently Supported Features

The following features are already available in MiniMCP.

- 🧩 Server primitives - Tools, Prompts and Resources
- 🔗 Transports - stdio, HTTP, Streamable HTTP
- 🔄 Server to client messages - Progress notification
- 🛠 Typed scope and handler context
- ⚡ Asynchronous and stateless message processing
- 📝 Easy handler registration for different MCP message types
- ⏱️ Enforces idle time and concurrency limits
- 📦 Web frameworks — In-built support for Starlette/FastAPI

### Planned Features (if needed)

These features may be added in the future if need arises.

- ⚠️ Built-in support for more frameworks — Flask, Django etc.
- ⚠️ Client primitives - Sampling, Elicitation, Logging
- ⚠️ Resumable Streamable HTTP with GET method support
- ⚠️ Pagination
- ⚠️ Authentication
- ⚠️ MCP Client (_As shown in the [integration tests](../../tests/server/minimcp/integration/), MiniMCP (All 3 transports) works seamlessly with existing MCP clients, hence there is no immediate need for a custom client_)

### Unlikely Features

Only feature that's not expected to be built into MiniMCP in the foreseeable future.

- 🚫 Session management

## Using MiniMCP

The snippets below provide a quick overview of how to use MiniMCP. Check out the [examples](../examples/minimcp/) for more.

### Installation

```bash
pip install mcp
```

### Basic Setup

The following example demonstrates simple registration and basic message processing using the handle function.

```python
from mcp.server.minimcp import MiniMCP


mcp = MiniMCP(name="MathServer")

# Tool
@mcp.tool()
def add(a:int, b:int) -> int:
    "Add two numbers"
    return a + b

# Prompt
@mcp.prompt()
def problem_solving(problem_description: str) -> str:
    "Prompt to systematically solve math problems."
    return f"""You are a math problem solver. Solve the following problem step by step.
Problem: {problem_description}
"""

# Resource
@mcp.resource("math://constants/pi")
def pi_value() -> float:
    """Value of π (pi) to be used"""
    return 3.14

request_msg = '{"jsonrpc": "2.0", "id": "1", "method": "ping"}'
response_msg = await mcp.handle(request_msg, scope={...})
# response_msg = '{"jsonrpc": "2.0", "id": "1", "result": {}}'
```
### Standalone ASGI App

MiniMCP can be easily deployed as an ASGI application.

```python
from fastapi import FastAPI, Request
from mcp.server.minimcp import MiniMCP, HTTPTransport

# Create an MCP instance
mcp = MiniMCP(name="MathServer")

# Register tools and other primitives
@mcp.tool(description="Add two numbers")
def add(a:int, b:int) -> int:
    return a + b

# MCP server as ASGI Application
app = HTTPTransport(mcp).as_starlette("/mcp")
```

You can now start the server using uvuicorn with four workers as follows.
```bash
uv run uvicorn test:app --workers 4
```

### FastAPI Integration

This minimal example shows how to expose an MCP tool over HTTP using FastAPI.

```python
from fastapi import FastAPI, Request
from mcp.server.minimcp import MiniMCP, HTTPTransport

# This can be an existing FastAPI/Starlette app (with authentication, middleware, etc.)
app = FastAPI()

# Create an MCP instance
mcp = MiniMCP[dict](name="MathServer")

# Register a simple tool
@mcp.tool(description="Add two numbers")
def add(a:int, b:int) -> int:
    return a + b

# Host MCP server
@app.post("/mcp")
async def mcp(request: Request):
    scope = {...} # Pass auth, database and mother metadata as part of scope
    return await mcp_transport.starlette_dispatch(request, scope)
```

## API Reference

This section provides an overview of the key classes, their functions, and the arguments they accept.

### MiniMCP

As the name suggests, MiniMCP is the key class for creating a server. It requires a server name as its only mandatory argument; all other arguments are optional. You can also specify the type of the scope object, which is passed through the system for static type checking.

MiniMCP provides:

- Tool, Prompt, and Resource managers — used to register message handlers.
- A Context manager — usable inside handlers.

The `MiniMCP.handle()` function processes incoming messages. It accepts a JSON-RPC 2.0 message string and two optional parameters — a send function and a scope object.

MiniMCP controls how many handlers can run at the same time and how long each handler can remain idle. By default, idle_timeout is set to 30 seconds and max_concurrency to 100.

```python
# Instantiation
mcp = MiniMCP[ScopeT](name, [version, instructions, idle_timeout, max_concurrency])

# Managers
mcp.tool
mcp.prompt
mcp.resource
mcp.context

# Message handling
response = await mcp.handle(message, [send, scope])
```

### Primitive Managers/Decorators

MiniMCP supports three server primitives, each managed by its own manager class. These managers are available under MiniMCP as a callable instance that can be used as decorators for registering handler functions. They work similar to FastMCP's decorators.

The decorator accepts primitive details as argument (like name, description etc). If not provided, these details are automatically inferred from the handler function.

In addition to decorator usage, all three primitive managers also expose methods to add, list, remove, and invoke handlers programmatically.

#### Tool Manager

```python
# As a decorator
@mcp.tool([name, title, description, annotations, meta])
def handler_func(...):...

# Methods for programmatic access
mcp.tool.add(handler_func, [name, title, description, annotations, meta])  # Register a tool
mcp.tool.remove(name)                                                      # Remove a tool by name
mcp.tool.list()                                                            # List all registered tools
mcp.tool.call(name, args)                                                  # Invoke a tool by name
```

#### Prompt Manager

```python
# As a decorator
@mcp.prompt([name, title, description, meta])
def handler_func(...):...

# Methods for programmatic access
mcp.prompt.add(handler_func, [name, title, description, meta])
mcp.prompt.remove(name)
mcp.prompt.list()
mcp.prompt.get(name, args)
```

#### Resource Manager

```python
# As a decorator
@mcp.resource(url, [name, title, description, mime_type, annotations, meta])
def handler_func(...):...

# Methods for programmatic access
mcp.resource.add(handler_func, url, [name, title, description, annotations, meta])
mcp.resource.remove(name)
mcp.resource.list()
mcp.resource.list_templates()
mcp.resource.read(uri)
mcp.resource.read_by_name(name, args)
```

### Context Manager

The Context Manager provides access to request metadata (such as the message, scope, responder, and time_limiter) directly inside the handler function. It tracks the currently active handler context, which you can retrieve using `mcp.context.get()`. If called outside of a handler, this method raises a `ContextError`.

```python
# Context structure
Context(Generic[ScopeT]):
    message: JSONRPCMessage      # The parsed request message
    time_limiter: TimeLimiter    # time_limiter.reset() resets the handler idle timeout
    scope: ScopeT | None         # Scope object passed when calling handle()
    responder: Responder | None  # Allows sending notifications back to the client

# Accessing context
mcp.context.get() -> Context[ScopeT]

# Following helpers are also provided by context for easy access
mcp.context.get_scope() -> ScopeT
mcp.context.get_responder() -> Responder
```

## Transports

The official MCP specification currently defines two standard transport mechanisms: [stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#stdio) and [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#streamable-http). It also provides flexibility in implementations and also permits custom transports. MiniMCP uses this flexibility to introduce a third option: [HTTP transport](../docs/minimcp-transport-specification-compliance.md#2-http-transport).

| Transport       | Directionality   | Use Case                                                            |
| --------------- | ---------------- | ------------------------------------------------------------------- |
| stdio           | Bidirectional    | Local integration (e.g., Claude desktop)                            |
| HTTP            | Request–response | Simple REST-like message handling                                   |
| Streamable HTTP | Bidirectional    | Advanced message handling with notifications, progress updates etc. |

HTTP is a subset of Streamable HTTP and does not support bidirectional (server-to-client) communication. However, as shown in the integration example, it can be added as an API endpoint in any Python application to host remote MCP servers. Importantly, it remains compatible with Streamable HTTP MCP clients.

MiniMCP provides a `Smart Streamable HTTP` implementation that adapts to usage pattern — if the handler simply returns a message, the server replies with a normal JSON HTTP response. An event stream is opened only when the server needs to push notifications to the client. To keep things simple and stateless, the current implementation uses polling to keep the stream alive. Resumability in case of connection loss could be implemented in a future iteration.

Check out [the Math MCP examples](../../examples/minimcp/math_mcp/) to see how each transport can be used.

## Testing

MiniMCP comes with a comprehensive test suite of **645 tests** covering unit and integration testing across all components. The test suite validates MCP specification compliance, error handling, edge cases, and real-world scenarios.

For detailed information about the test suite, coverage, and running tests, see the [Testing Documentation](./testing.md).

## Error Handling

MiniMCP implements a comprehensive error handling system following JSON-RPC 2.0 and MCP specifications. It is designed to bubble up the error information to the client and continue processing. Its architecture cleanly distinguishes between external, client-exposed errors (MiniMCPError subclasses) and internal, MCP-handled errors (InternalMCPError subclasses).

### Protocol-Level Errors

The `MiniMCP.handle()` method provides centralized error handling for all protocol-level errors. Parse errors and JSON-RPC validation errors are re-raised as `InvalidMessageError`, which transport layers must handle explicitly. Other internal errors (invalid parameters, method not found, resource not found, runtime errors etc.) are caught and returned as formatted JSON-RPC error responses with appropriate error codes per the specification.

Tool errors use a dual mechanism as specified by MCP:
1. Tool registration errors, invalid arguments, and runtime failures are returned as JSON-RPC errors.
2. Business logic errors within tool handlers (e.g., API failures, invalid data) are caught by the low-level MCP core and returned in `CallToolResult` with `isError: true`, allowing the client to handle them appropriately.

### Transport Error Handling

Each transport implements error handling tailored to its communication model:
- **HTTP transports**: Performs request (header/version) validation, and catches `InvalidMessageError` and other unexpected exceptions. The errors are then formatted as JSON-RPC error messages and return with appropriate HTTP status codes.
- **Stdio transport**: Catches all exceptions including `InvalidMessageError`, formats them as JSON-RPC errors, and writes them to stdout. The connection remains active to continue processing subsequent messages.

## Examples

To run the examples, you’ll need a development setup. After cloning this repository, run the following command from the project root to set up the environment:

```bash
uv sync --frozen --all-extras --dev
```

### 1. Math MCP server

[First set of example](../../examples/minimcp/math_mcp/) include a [Math MCP server](../examples/minimcp/math_mcp/math_mcp.py) with prompts, resources and four tools (add, subtract, multiply, and divide). The example demonstrate how MiniMCP works with different transport mechanisms and frameworks.

The table below lists the available examples along with the commands to run them.

| # | Transport/Server       | Command                                                               |
|---|------------------------|-----------------------------------------------------------------------|
| 1 | Stdio                  | `uv run -m examples.minimcp.math_mcp.stdio_server`                    |
| 2 | HTTP Server            | `uv run uvicorn examples.minimcp.math_mcp.http_server:app`            |
| 3 | Streamable HTTP Server | `uv run uvicorn examples.minimcp.math_mcp.streamable_http_server:app` |

#### Claude Desktop

Claude desktop can be configured as follows to run the Math MCP stdio example.

```json
{
    "mcpServers":
    {
        "math-server":
        {
            "command": "uv",
            "args":
            [
                "--directory",
                "/path/to/minimcp",
                "run",
                "-m",
                "examples.minimcp.math_mcp_server.stdio"
            ]
        }
    }
}
```

### 2. Integrating With Web Frameworks

[Second set of examples](../../examples/minimcp/web_frameworks/) demonstrate how MiniMCP can be integrated with web frameworks like FastAPI and Django. A dummy [Issue Tracker MCP server](../../examples/minimcp/web_frameworks/issue_tracker_mcp.py) was created for the same. It provides tools to create, read, and delete issues.

The table below lists the available examples along with the commands to run them.

| # | Server                         | Command                                                                                            |
|---|--------------------------------|----------------------------------------------------------------------------------------------------|
| 1 | FastAPI HTTP Server with auth | `uv run --with fastapi uvicorn examples.minimcp.web_frameworks.fastapi_http_server_with_auth:app` |
| 2 | Django WSGI server with auth   | `uv run --with django --with djangorestframework python examples/minimcp/web_frameworks/django_wsgi_server_with_auth.py runserver` |

## License

This project is licensed under the MIT License - see the LICENSE file for details.
