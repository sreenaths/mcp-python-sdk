# MiniMCP Test Suite Documentation

## Overview

The MiniMCP test suite is a comprehensive collection of over **645 tests**, organized into unit and integration tests. The test suite ensures the reliability, correctness, and MCP specification compliance of the MiniMCP framework.

### Test Statistics

- **Total Tests**: 645
- **Unit Tests**: 514 (80%)
- **Integration Tests**: 131 (20%)
- **Test Files**: 16

## Test Structure

```text
tests/server/minimcp/
├── unit/                          # Unit tests (514 tests)
│   ├── managers/                  # Manager component tests
│   │   ├── test_context_manager.py
│   │   ├── test_prompt_manager.py
│   │   ├── test_resource_manager.py
│   │   └── test_tool_manager.py
│   ├── transports/                # Transport layer tests
│   │   ├── test_base_http_transport.py
│   │   ├── test_http_transport.py
│   │   ├── test_stdio_transport.py
│   │   └── test_streamable_http_transport.py
│   ├── utils/                     # Utility tests
│   │   ├── test_json_rpc.py       # JSON-RPC protocol tests
│   │   └── test_mcp_func.py       # MCP function wrapper tests
│   ├── test_limiter.py            # Rate limiting tests
│   ├── test_minimcp.py            # Core MiniMCP tests
│   └── test_responder.py          # Responder tests
│
└── integration/                   # Integration tests (131 tests)
    ├── helpers/                   # Test helpers
    │   ├── client_session_with_init.py
    │   ├── http.py
    │   └── process.py
    ├── servers/                   # Test servers
    │   ├── http_server.py
    │   ├── math_mcp.py
    │   └── stdio_server.py
    ├── test_http_server.py
    ├── test_stdio_server.py
    └── test_streamable_http_server.py
```

## Unit Tests (514 tests)

### Core Components

#### 1. MiniMCP Core (`test_minimcp.py`)

**50 test cases** | **840 lines**

Tests the main `MiniMCP` class, which is the central orchestrator of the framework.

**Test Classes**:

- `TestMiniMCP` - Core functionality tests
- `TestMiniMCPIntegration` - Integration scenarios

**Coverage**:

- ✅ Server initialization and configuration
- ✅ Message handling (requests, notifications, responses)
- ✅ Protocol version negotiation
- ✅ Client capabilities management
- ✅ Lifecycle management (initialize, shutdown)
- ✅ Error handling and validation
- ✅ Context management
- ✅ Manager coordination (Tools, Resources, Prompts)
- ✅ Concurrency control
- ✅ Timeout handling

**Key Test Scenarios**:

```python
# Initialization
test_init_creates_minimcp_instance()
test_init_with_custom_configuration()
test_init_with_lowlevel_server()

# Message Processing
test_handle_valid_request_message()
test_handle_notification_message()
test_handle_invalid_json()
test_handle_malformed_jsonrpc()

# Lifecycle
test_initialize_request()
test_shutdown_gracefully()
test_ping_pong()
```

#### 2. Responder (`test_responder.py`)

**35 test cases** | **639 lines**

Tests the `Responder` class responsible for building JSON-RPC responses.

**Test Classes**:

- `TestResponder` - Response building tests
- `TestResponderIntegration` - End-to-end response scenarios

**Coverage**:

- ✅ Success response building
- ✅ Error response creation
- ✅ Result serialization
- ✅ Progress notification support
- ✅ Time limiting integration
- ✅ Notification handling
- ✅ Error code mapping (MCP errors → JSON-RPC errors)

**Key Features Tested**:

```python
# Response Types
test_success_response()
test_error_response()
test_notification_response()

# Special Features
test_progress_notifications()
test_timeout_handling()
test_result_serialization()
```

#### 3. JSON-RPC Protocol (`test_json_rpc.py`)

**41 test cases** | **476 lines**

Comprehensive testing of JSON-RPC 2.0 protocol implementation.

**Test Classes**:

- `TestBuildErrorMessage` - Error message construction
- `TestGetRequestId` - Request ID extraction
- `TestIsInitializeRequest` - Initialize request detection
- `TestCheckJsonrpcVersion` - Version validation
- `TestJSONRPCEnvelope` - Message envelope handling
- `TestIntegration` - Protocol integration tests

**Coverage**:

- ✅ JSON-RPC 2.0 specification compliance
- ✅ Request/response message building
- ✅ Error code mapping (-32700 to -32603, -32000 to -32099)
- ✅ Message validation
- ✅ ID handling (string, number, null)
- ✅ Batch request support
- ✅ Notification detection (no ID)
- ✅ Version checking ("2.0" enforcement)

**Error Code Coverage**:

```python
# Standard JSON-RPC Errors
-32700  # Parse error
-32600  # Invalid Request
-32601  # Method not found
-32602  # Invalid params
-32603  # Internal error

# MCP-Specific Errors
-32000  # Server error
-32001  # Connection error
-32002  # Request timeout
```

#### 4. Rate Limiting (`test_limiter.py`)

**39 test cases** | **533 lines**

Tests the rate limiting and timeout enforcement mechanisms.

**Test Classes**:

- `TestTimeLimiter` - Time-based limiting
- `TestLimiter` - General rate limiting
- `TestLimiterIntegration` - Integration scenarios

**Coverage**:

- ✅ Time-based request limiting
- ✅ Concurrent request limiting
- ✅ Request timeout enforcement
- ✅ Limiter reset and cleanup
- ✅ Multi-threaded safety
- ✅ Memory efficiency
- ✅ Edge cases (zero timeout, negative values)

### Manager Components

#### 5. Tool Manager (`test_tool_manager.py`)

**46 test cases** | **829 lines**

Tests the `ToolManager` which handles tool registration and execution.

**Test Classes**:

- `TestToolManager` - Core tool management
- `TestToolManagerAdvancedFeatures` - Advanced features

**Coverage**:

- ✅ Tool registration (sync and async functions)
- ✅ Tool listing with pagination
- ✅ Tool execution
- ✅ Input schema generation from type hints
- ✅ Pydantic model validation
- ✅ Tool metadata (name, description)
- ✅ Error handling in tool execution
- ✅ Dynamic tool registration/unregistration
- ✅ Tool name inference
- ✅ Cursor/pagination support

**Key Scenarios**:

```python
# Registration
test_register_sync_function()
test_register_async_function()
test_register_with_pydantic_model()

# Execution
test_execute_tool_success()
test_execute_tool_with_validation_error()
test_execute_nonexistent_tool()

# Schema Generation
test_schema_from_type_hints()
test_schema_from_pydantic_model()
```

#### 6. Resource Manager (`test_resource_manager.py`)

**63 test cases** | **1,089 lines**

Tests the `ResourceManager` which handles resource registration and access.

**Test Classes**:

- `TestResourceManager` - Core resource management
- `TestResourceManagerAdvancedFeatures` - Advanced features

**Coverage**:

- ✅ Resource registration (static and dynamic)
- ✅ Resource templates with URI patterns
- ✅ Resource listing with pagination
- ✅ Resource reading (text and blob)
- ✅ MIME type handling
- ✅ Resource subscriptions
- ✅ Dynamic resource updates
- ✅ URI template expansion
- ✅ Cursor/pagination support
- ✅ Metadata and annotations

**Resource Types Tested**:

```python
# Static Resources
test_register_static_resource()
test_read_text_resource()
test_read_blob_resource()

# Dynamic Resources (Templates)
test_register_resource_template()
test_template_uri_matching()
test_dynamic_resource_generation()

# Subscriptions
test_subscribe_to_resource()
test_unsubscribe_from_resource()
test_resource_update_notification()
```

#### 7. Prompt Manager (`test_prompt_manager.py`)

**51 test cases** | **918 lines**

Tests the `PromptManager` which handles prompt registration and generation.

**Test Classes**:

- `TestPromptManager` - Core prompt management
- `TestPromptManagerAdvancedFeatures` - Advanced features

**Coverage**:

- ✅ Prompt registration (sync and async)
- ✅ Prompt listing with pagination
- ✅ Prompt execution with arguments
- ✅ Argument schema generation
- ✅ Dynamic prompts
- ✅ Pydantic model arguments
- ✅ Cursor/pagination support
- ✅ Error handling
- ✅ Metadata management

**Prompt Features Tested**:

```python
# Registration
test_register_sync_prompt()
test_register_async_prompt()
test_register_with_arguments()

# Execution
test_get_prompt_with_args()
test_get_prompt_validation_error()

# Argument Schemas
test_schema_from_type_hints()
test_schema_from_pydantic()
```

#### 8. Context Manager (`test_context_manager.py`)

**17 test cases** | **246 lines**

Tests the `ContextManager` which handles server context and state.

**Test Classes**:

- `TestContext` - Context object tests
- `TestContextManager` - Context management tests

**Coverage**:

- ✅ Context creation and initialization
- ✅ Context lifecycle management
- ✅ State isolation between contexts
- ✅ Context cleanup
- ✅ Thread safety
- ✅ Scope management (generic type support)

### Transport Layer Tests

#### 9. Base HTTP Transport (`test_base_http_transport.py`)

**22 test cases** | **281 lines**

Tests the base HTTP transport implementation that serves as the foundation for both HTTP and Streamable HTTP transports.

**Test Classes**:

- `TestBaseHTTPTransport` - Core base HTTP transport
- `TestBaseHTTPTransportHeaderValidation` - Header validation

**Coverage**:

- ✅ Basic request/response handling
- ✅ Content-Type validation (`application/json`)
- ✅ Accept header validation
- ✅ Protocol version validation (`MCP-Protocol-Version` header)
- ✅ HTTP method validation
- ✅ Header parsing (case-insensitive, quality values)
- ✅ Error response handling
- ✅ Request validation errors

**Key Features Tested**:

```python
# Header Validation
test_validate_content_type()
test_validate_accept_headers()
test_validate_protocol_version()

# Request Handling
test_handle_valid_request()
test_handle_invalid_method()
test_handle_missing_headers()
```

#### 10. HTTP Transport (`test_http_transport.py`)

**39 test cases** | **529 lines**

Tests the basic HTTP transport implementation.

**Test Classes**:

- `TestHTTPTransport` - Core HTTP transport
- `TestHTTPTransportHeaderValidation` - Header validation

**Coverage**:

- ✅ POST request handling
- ✅ Content-Type validation (`application/json`)
- ✅ Accept header validation
- ✅ Protocol version validation (`MCP-Protocol-Version` header)
- ✅ Method not allowed (only POST supported)
- ✅ Error response handling
- ✅ NoMessage handling (notifications)
- ✅ Header parsing (case-insensitive, quality values, charset)
- ✅ Edge cases (empty body, malformed JSON, missing headers)

**HTTP Validation Tested**:

```python
# Request Validation
test_validate_content_type()
test_validate_accept_headers()
test_validate_protocol_version()

# Error Scenarios
test_invalid_content_type()
test_invalid_accept_header()
test_unsupported_method()
test_malformed_body()
```

#### 11. Streamable HTTP Transport (`test_streamable_http_transport.py`)

**43 test cases** | **846 lines**

Tests the streamable HTTP transport with SSE (Server-Sent Events) support.

**Test Classes**:

- `TestStreamableHTTPTransport` - Core streamable transport
- `TestStreamableHTTPTransportHeaderValidation` - Header validation
- `TestStreamableHTTPTransportEdgeCases` - Edge cases
- `TestStreamableHTTPTransportBase` - Base transport inheritance validation

**Coverage**:

- ✅ All HTTPTransport features (inherits)
- ✅ SSE (Server-Sent Events) support
- ✅ Bidirectional Accept headers (`application/json` + `text/event-stream`)
- ✅ Stream lifecycle management
- ✅ Concurrent request handling
- ✅ Stream cleanup and resource management
- ✅ Early disconnect handling
- ✅ Task group management
- ✅ Context manager requirements

**Streaming Features Tested**:

```python
# SSE Support
test_sse_response_format()
test_sse_with_unicode()
test_streaming_with_final_response()

# Resource Management
test_stream_cleanup_on_error()
test_stream_cleanup_without_consumer()
test_stream_cleanup_on_early_disconnect()

# Lifecycle
test_transport_context_manager()
test_concurrent_request_handling()
```

#### 12. Stdio Transport (`test_stdio_transport.py`)

**15 test cases** | **302 lines**

Tests the standard input/output transport for CLI applications.

**Test Classes**:

- `TestWriteMsg` - Message writing tests
- `TestDispatch` - Message dispatch tests
- `TestRun` - Transport execution tests

**Coverage**:

- ✅ Line-based message reading (newline delimited)
- ✅ Message writing with newline validation
- ✅ Empty line handling
- ✅ Concurrent message processing
- ✅ Send callback support
- ✅ NoMessage handling
- ✅ MCP spec compliance (no embedded newlines)

**Stdio Protocol Tested**:

```python
# Message Format
test_write_msg_adds_newline()
test_rejects_embedded_newlines()
test_rejects_carriage_returns()

# Processing
test_run_relays_messages()
test_concurrent_message_handling()
test_handler_can_use_send_callback()
```

### Utility Tests

#### 13. MCP Function Wrapper (`test_mcp_func.py`)

**53 test cases** | **745 lines**

Tests the `MCPFunc` wrapper that converts Python functions into MCP-compatible tools/prompts.

**Test Classes**:

- `TestMCPFuncValidation` - Input validation
- `TestMCPFuncNameInference` - Name extraction
- `TestMCPFuncSchemas` - Schema generation
- `TestMCPFuncExecution` - Function execution
- `TestMCPFuncEdgeCases` - Edge cases
- `TestMCPFuncIntegration` - Integration scenarios
- `TestMCPFuncMemoryAndPerformance` - Performance tests

**Coverage**:

- ✅ Function wrapping (sync and async)
- ✅ Name inference from function names
- ✅ JSON Schema generation from type hints
- ✅ Pydantic model support
- ✅ Default value handling
- ✅ Optional parameter handling
- ✅ Docstring parsing
- ✅ Method binding preservation
- ✅ Exception handling
- ✅ Memory efficiency

**Schema Generation Coverage**:

```python
# Type Hint Support
test_schema_for_int()
test_schema_for_str()
test_schema_for_bool()
test_schema_for_float()
test_schema_for_list()
test_schema_for_dict()
test_schema_for_optional()
test_schema_for_union()

# Pydantic Models
test_schema_from_pydantic_model()
test_nested_pydantic_models()
```

## Integration Tests (131 tests)

### Server Integration Tests

#### 14. HTTP Server Integration (`test_http_server.py`)

**39 test cases** | **570 lines**

End-to-end testing of HTTP server with real MCP client.

**Test Class**:

- `TestHttpServer` - Full HTTP server scenarios

**Coverage**:

- ✅ Server startup and shutdown
- ✅ Initialize handshake
- ✅ Tool listing and execution
- ✅ Resource listing and reading
- ✅ Prompt listing and execution
- ✅ Error handling
- ✅ Concurrent requests
- ✅ Client-server communication

#### 15. Streamable HTTP Server Integration (`test_streamable_http_server.py`)

**55 test cases** | **286 lines**

End-to-end testing of streamable HTTP server with SSE support.

**Test Class**:

- `TestStreamableHttpServer` - Full streamable HTTP scenarios

**Coverage**:

- ✅ All HTTP server features (inherits)
- ✅ SSE event streaming
- ✅ Progress notifications
- ✅ Long-running operations
- ✅ Stream lifecycle

#### 16. Stdio Server Integration (`test_stdio_server.py`)

**37 test cases** | **516 lines**

End-to-end testing of stdio-based server.

**Test Class**:

- `TestStdioServer` - Full stdio server scenarios

**Coverage**:

- ✅ Process-based server execution
- ✅ Line-based communication
- ✅ Tool, resource, and prompt operations
- ✅ Error scenarios
- ✅ Graceful shutdown

### Integration Test Helpers

**Helper Modules**:

- `helpers/client_session_with_init.py` - Client session management
- `helpers/http.py` - HTTP test utilities
- `helpers/process.py` - Process management for stdio tests

**Test Servers**:

- `servers/math_mcp.py` - Math operations server for testing
- `servers/http_server.py` - HTTP server launcher
- `servers/stdio_server.py` - Stdio server launcher

## Test Coverage Highlights

### MCP Specification Compliance

The test suite extensively validates compliance with the MCP specification:

- ✅ **Protocol Negotiation**: Version checking, capability negotiation
- ✅ **Message Format**: JSON-RPC 2.0 compliance
- ✅ **Transport Protocols**: HTTP, Streamable HTTP (SSE), Stdio
- ✅ **Lifecycle**: Initialize, ping, shutdown
- ✅ **Primitives**: Tools, Resources, Prompts
- ✅ **Error Handling**: Proper error codes and messages
- ✅ **Pagination**: Cursor-based pagination support
- ✅ **Subscriptions**: Resource subscription notifications

### Edge Cases and Error Handling

- ✅ Malformed JSON
- ✅ Invalid JSON-RPC messages
- ✅ Missing required fields
- ✅ Invalid method names
- ✅ Timeout scenarios
- ✅ Concurrent request handling
- ✅ Resource cleanup
- ✅ Unicode handling
- ✅ Large payloads
- ✅ Empty inputs
- ✅ Validation errors

### Performance and Reliability

- ✅ Concurrent execution tests
- ✅ Memory leak detection
- ✅ Resource cleanup verification
- ✅ Timeout enforcement
- ✅ Rate limiting
- ✅ Stream lifecycle management

## Running Tests

### Run All Tests

```bash
# Run all MiniMCP tests
uv run pytest tests/server/minimcp/

# Run with coverage
uv run pytest tests/server/minimcp/ --cov=mcp.server.minimcp --cov-report=html
```

### Run Specific Test Suites

```bash
# Unit tests only
uv run pytest tests/server/minimcp/unit/

# Integration tests only
uv run pytest tests/server/minimcp/integration/

# Specific component
uv run pytest tests/server/minimcp/unit/test_minimcp.py
uv run pytest tests/server/minimcp/unit/managers/
uv run pytest tests/server/minimcp/unit/transports/
```

### Run Specific Test Class or Method

```bash
# Specific test class
uv run pytest tests/server/minimcp/unit/test_minimcp.py::TestMiniMCP

# Specific test method
uv run pytest tests/server/minimcp/unit/test_minimcp.py::TestMiniMCP::test_init_creates_minimcp_instance
```

### Test Options

```bash
# Verbose output
uv run pytest tests/server/minimcp/ -v

# Show print statements
uv run pytest tests/server/minimcp/ -s

# Run in parallel
uv run pytest tests/server/minimcp/ -n auto

# Stop on first failure
uv run pytest tests/server/minimcp/ -x

# Run only failed tests from last run
uv run pytest tests/server/minimcp/ --lf
```

## Test Quality Metrics

### Code Quality

- ✅ **Type Hints**: All test code uses type hints
- ✅ **Fixtures**: Extensive use of pytest fixtures for reusability
- ✅ **Mocking**: Proper use of `unittest.mock` for isolation
- ✅ **Async Support**: Full support for async test functions
- ✅ **Docstrings**: Clear documentation for test purpose

### Test Organization

- ✅ **Logical Grouping**: Tests organized by component and feature
- ✅ **Naming Convention**: Clear, descriptive test names
- ✅ **Test Isolation**: Each test is independent
- ✅ **Setup/Teardown**: Proper use of fixtures for setup/cleanup
- ✅ **Markers**: Uses `pytest.mark.anyio` for async tests

## Contributing to Tests

When adding new features to MiniMCP, please ensure:

1. **Unit tests** for the component logic
2. **Integration tests** for end-to-end scenarios (if applicable)
3. **Edge case coverage** for error conditions
4. **Documentation** of what the test validates
5. **Fixtures** for reusable test setup
6. **Type hints** for all test code
7. **Async tests** properly marked with `@pytest.mark.anyio`

### Test Template

```python
import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.anyio


class TestMyFeature:
    """Test suite for MyFeature class."""

    @pytest.fixture
    def my_fixture(self):
        """Create a test fixture."""
        return MyObject()

    async def test_feature_success(self, my_fixture):
        """Test successful feature execution."""
        result = await my_fixture.do_something()
        assert result == expected_value

    async def test_feature_error_handling(self, my_fixture):
        """Test error handling in feature."""
        with pytest.raises(ExpectedError):
            await my_fixture.do_invalid_thing()
```

## Test Dependencies

The test suite uses:

- `pytest` - Test framework
- `pytest-anyio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-xdist` - Parallel test execution
- `unittest.mock` - Mocking support

## Summary

The MiniMCP test suite is a comprehensive, well-organized collection of 645 tests that ensure:

- ✅ **MCP Specification Compliance**: Full adherence to protocol requirements
- ✅ **Reliability**: Extensive error handling and edge case coverage
- ✅ **Maintainability**: Clear organization and documentation
- ✅ **Performance**: Concurrent execution and resource management validation
- ✅ **Quality**: High code quality with type hints and best practices

The test suite provides confidence that MiniMCP correctly implements the Model Context Protocol and handles real-world scenarios effectively.

---

*Generated by: Calude 4.5 Sonnet*\
*Last updated: December 6, 2025*
