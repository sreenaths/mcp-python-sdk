# MiniMCP Specification Compliance

## Primitives

Primitives are the fundamental building blocks for adding context to language models via MCP. They enable rich interactions between clients, servers, and language models.

### 1. Prompts

Prompts in MCP provide a standardized way for servers to expose prompt templates to clients. According to the [official specification](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts), prompts allow servers to provide structured messages and instructions for interacting with language models. Clients can discover available prompts, retrieve their contents, and provide arguments to customize them.

Prompts are designed to be user-controlled, exposed from servers to clients with the intention of the user being able to explicitly select them for use. Typically, prompts are triggered through user-initiated commands in the user interface, such as slash commands in chat applications.

MiniMCP fully implements the core prompts specification with the following compliance:

#### Prompts - Core Protocol Messages

**Fully Supported:**

- `prompts/list` - Lists all available prompts with their metadata
- `prompts/get` - Retrieves a specific prompt by name with provided arguments

#### Prompts User Interaction Model

Prompts are user-controlled and typically exposed in client UIs as selectable options:

- Designed for explicit user selection (e.g., slash commands)
- User-initiated invocation through interface commands
- Display names (title) for improved UX in client applications

#### Prompts Data Types

**Prompt Definition:**

- `name`: Unique identifier for the prompt (automatically inferred from function name)
- `title`: Optional human-readable name for display purposes (e.g., "🔍 Request Code Review")
- `description`: Optional human-readable description (falls back to function docstring)
- `arguments`: List of PromptArgument for customization

**Prompt Arguments:**

- `name`: Parameter name
- `description`: Optional parameter description
- `required`: Boolean flag indicating if argument is required
- Arguments are automatically inferred from function signature with type annotations

**Prompt Messages:**

- `role`: Either "user" or "assistant" to indicate the speaker
- `content`: Supports multiple content types per specification

#### Prompts Content Types

PromptMessages support all content types defined in the MCP specification:

**Text Content (type: "text"):**

- Most common for natural language interactions
- Plain text messages with optional annotations

**Image Content (type: "image"):**

- Base64-encoded image data
- MIME type specification required
- Enables multi-modal interactions

**Audio Content (type: "audio"):**

- Base64-encoded audio data
- MIME type specification required
- Supports audio context in prompts

**Embedded Resources (type: "resource"):**

- Server-side resources directly in messages
- Includes URI, MIME type, and content
- Enables seamless incorporation of reference materials

All content types support optional annotations for metadata about audience, priority, and modification times.

#### Message Conversion

Handler functions can return multiple formats, automatically converted to PromptMessage:

- `str` → User message with text content
- `PromptMessage` → Used as-is with role and content
- `dict` → Validated as PromptMessage
- `list/tuple` → Multiple messages
- Other types → JSON-serialized to text content

#### Prompts Capabilities Declaration

The server properly declares prompt capabilities in the initialization response:

```json
{
  "prompts": {
    "listChanged": false
  }
}
```

The `listChanged` flag indicates whether the server emits notifications when the prompt list changes.

#### Argument Validation

MiniMCP validates prompt arguments before execution:

- Checks for required arguments
- Validates argument presence against prompt definition
- Returns appropriate error codes for missing arguments per specification

#### Prompts Error Handling

MiniMCP follows the specification's error handling requirements:

- Invalid prompt name: Error code `-32602` (Invalid params)
- Missing required arguments: Error code `-32602` (Invalid params)
- Internal errors: Error code `-32603` (Internal error)
- Proper error messages with context

#### Optional Features (Not Fully Implemented)

**Pagination:**

- The specification states that `prompts/list` supports pagination
- Current implementation returns all prompts without pagination
- Infrastructure exists in lowlevel server for future support

**List Changed Notifications:**

- The specification defines optional `notifications/prompts/list_changed`
- MiniMCP has capability infrastructure but disabled by default (`listChanged: false`)
- Can be enabled for future use cases requiring dynamic prompt lists

**Completion API:**

- The specification mentions argument auto-completion through completion API
- Not currently implemented (marked as TODO)
- Would enable enhanced argument suggestions in clients

#### Prompts Implementation Considerations

Per the specification, MiniMCP:

- Validates prompt arguments before processing ✅
- Handles both synchronous and asynchronous handler functions ✅
- Supports proper capability negotiation ✅
- Implements user-controlled interaction model ✅

#### Prompts Security

MiniMCP carefully validates all prompt inputs and outputs to prevent injection attacks or unauthorized access, as required by the specification.

**Compliance Summary:** MiniMCP achieves ~95% specification compliance for prompts, with all mandatory features fully implemented. The missing features (pagination, list change notifications, completion API) are either optional per the specification or represent future enhancements.

### 2. Resources

Resources in MCP provide a standardized way for servers to expose data that provides context to language models. According to the [official specification](https://modelcontextprotocol.io/specification/2025-06-18/server/resources), each resource is uniquely identified by a URI and can represent files, database schemas, API responses, or any application-specific data. Resources are application-driven—host applications determine how to incorporate context based on their needs.

MiniMCP fully implements the core resource specification with the following compliance:

#### Resources - Core Protocol Messages

**Fully Supported:**

- `resources/list` - Lists all available static resources
- `resources/templates/list` - Lists all available resource templates with URI patterns
- `resources/read` - Reads resource content by URI (static or templated)

#### Resource Types

**Static Resources:**

- Fixed URI with no parameters (e.g., `file:///config.json`, `math://constants/pi`)
- Direct URI matching for resource lookup

**Resource Templates:**

- Parameterized URIs with placeholders (e.g., `file:///{path}`, `db://tables/{table}`)
- Automatic parameter extraction from URI patterns using regex
- URI parameters must exactly match function parameters
- Pattern matching with named capture groups

#### Resource Contents

**Text Content:**

- Returned as string with `text` field in the response
- Default MIME type: `text/plain`

**Binary Content:**

- Automatically base64-encoded per MCP specification
- Returned with `blob` field in the response
- Default MIME type: `application/octet-stream`

**Structured Data:**

- JSON-serializable objects automatically converted to text
- Returned as formatted JSON strings

#### Resources Annotations

Resources support optional annotations providing hints to clients:

- `audience`: Array of `["user", "assistant"]` indicating intended audience(s)
- `priority`: Number from 0.0 to 1.0 indicating importance (1.0 = most important)
- `lastModified`: ISO 8601 timestamp (e.g., `"2025-01-12T15:00:58Z"`)

#### URI Schemes

MiniMCP supports and documents common URI schemes per the specification:

- `file://` - Filesystem or filesystem-like resources
- `https://` - Web-accessible resources (when client can fetch directly)
- `git://` - Git version control integration
- Custom schemes following RFC 3986

Special MIME types:

- `inode/directory` - XDG MIME type for directory-like resources

#### Resources Capabilities Declaration

The server properly declares resource capabilities in the initialization response:

```json
{
  "resources": {
    "subscribe": false,
    "listChanged": false
  }
}
```

#### Optional Features (Not Implemented)

**Resource Subscriptions:**

- The specification defines optional `resources/subscribe` and `resources/unsubscribe` methods
- MiniMCP currently does not implement subscriptions (declared as `subscribe: false`)
- Infrastructure exists for future implementation

**List Changed Notifications:**

- The specification defines optional `notifications/resources/list_changed`
- MiniMCP has capability infrastructure but disabled by default (`listChanged: false`)
- Can be enabled for future use cases requiring dynamic resource lists

#### Resources Error Handling

MiniMCP follows the specification's error handling requirements:

- Resource not found: Error code `-32002` with appropriate message
- Internal errors: Error code `-32603`
- URI validation performed before resource operations
- Proper error messages with context (URI, resource name)

#### Resources - Security Considerations

Per the specification, MiniMCP:

- Validates all resource URIs before processing
- Encourages implementation-specific access controls for sensitive resources
- Properly encodes binary data (base64)
- Recommends permission checks before resource operations

**Compliance Summary:** MiniMCP achieves ~95% specification compliance for resources, with all mandatory features fully implemented. The missing features (subscriptions and list change notifications) are explicitly optional per the specification.

### 3. Tools

Tools in MCP allow servers to expose functionality that can be invoked by language models. According to the [official specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools), tools enable models to interact with external systems, such as querying databases, calling APIs, or performing computations. Each tool is uniquely identified by a name and includes metadata describing its schema.

Tools are designed to be model-controlled, meaning the language model can discover and invoke tools automatically based on its contextual understanding and the user's prompts. However, for trust & safety, there should always be a human in the loop with the ability to deny tool invocations.

MiniMCP fully implements the core tools specification with the following compliance:

#### Tools - Core Protocol Messages

**Fully Supported:**

- `tools/list` - Lists all available tools with their metadata
- `tools/call` - Invokes a specific tool by name with provided arguments

#### Tools User Interaction Model

Tools are model-controlled and can be invoked automatically by language models:

- Models discover and invoke tools based on contextual understanding
- Applications SHOULD provide UI that makes clear which tools are exposed to the AI model
- Applications SHOULD insert visual indicators when tools are invoked
- Applications SHOULD present confirmation prompts to users (human in the loop)

#### Tools Data Types

**Tool Definition:**

- `name`: Unique identifier for the tool (automatically inferred from function name)
- `title`: Optional human-readable name for display purposes in client UIs
- `description`: Human-readable description of functionality (falls back to function docstring)
- `inputSchema`: JSON Schema defining expected parameters (auto-generated from type annotations)
- `outputSchema`: Optional JSON Schema defining expected output structure (auto-generated when specified)
- `annotations`: Optional properties describing tool behavior (untrusted unless from trusted servers)

**Tool Results:**

Tools can return either unstructured or structured content:

- **Unstructured content**: Returned in the `content` field, can contain multiple content items
- **Structured content**: Returned in the `structuredContent` field as a JSON object
- **Combination**: Both unstructured and structured content in the same result

#### Tools Content Types

Tool results support multiple content types per the specification:

**Supported:**

- **Text Content** (`type: "text"`) - Plain text results
- **Image Content** (`type: "image"`) - Base64-encoded images with mimeType
- **Audio Content** (`type: "audio"`) - Base64-encoded audio with mimeType
- **Resource Links** (`type: "resource_link"`) - Links to resources that can be fetched by clients
- **Embedded Resources** (`type: "resource"`) - Full resource objects embedded in the result

All content types support optional annotations (audience, priority, lastModified) to provide metadata about the content.

#### Tools Annotations

Tool content supports the same annotation format used by resources and prompts:

- `audience`: Array specifying intended audience (e.g., ["user"], ["assistant"], ["user", "assistant"])
- `priority`: Float between 0 and 1 indicating importance (higher = more important)
- `lastModified`: ISO 8601 timestamp indicating when the content was last modified

#### Input/Output Schemas

MiniMCP automatically generates:

- `inputSchema`: JSON Schema from function type annotations using Pydantic models
- `outputSchema`: Optional JSON Schema for validating structured results

When an output schema is provided:

- Servers MUST provide structured results that conform to this schema
- Clients SHOULD validate structured results against this schema

#### Capabilities

MiniMCP declares the `tools` capability during initialization:

```json
{
  "capabilities": {
    "tools": {
      "listChanged": true
    }
  }
}
```

The `listChanged` indicator is configurable (default: true).

#### Error Handling

MiniMCP implements both error reporting mechanisms per the specification:

**1. Protocol Errors (JSON-RPC errors):**

- Unknown tools → `-32602` (Invalid params) via `InvalidParamsError`
- Server errors → `-32603` (Internal error) via `MCPRuntimeError`

**2. Tool Execution Errors:**

- API failures, invalid input data, business logic errors
- Returned in result with `isError: true`
- Handled by the lowlevel server

#### Optional Features

**List Changed Notifications:**

- ✅ Infrastructure exists with capability declaration
- ✅ Enabled by default (`listChanged: true`)
- `notifications/tools/list_changed` notification supported

**Pagination:**

- ⚠️ Mentioned in specification for `tools/list`
- ❌ Not currently implemented (returns all tools)
- Future enhancement opportunity

#### Tools Implementation Considerations

Per the specification, MiniMCP:

- Validates all tool inputs against inputSchema ✅
- Implements proper access controls via error handling ✅
- Rate limiting should be implemented at application level ⚠️
- Sanitizes tool outputs through content conversion ✅
- Handles both synchronous and asynchronous handler functions ✅
- Supports proper capability negotiation ✅

#### Tools Security

MiniMCP follows the security requirements from the specification:

**Server-side (MiniMCP):**

- Validates all tool inputs ✅
- Implements proper error handling and access controls ✅
- Sanitizes tool outputs ✅

**Client-side (Application responsibility):**

- Prompt for user confirmation on sensitive operations
- Show tool inputs to the user before calling the server (avoid data exfiltration)
- Validate tool results before passing to LLM
- Implement timeouts for tool calls
- Log tool usage for audit purposes

**Compliance Summary:** MiniMCP achieves ~98% specification compliance for tools, with all mandatory features fully implemented. The only missing feature is pagination for `tools/list`, which is mentioned but not strictly required per the specification.

## Transport

The official MCP specification currently defines two standard transport mechanisms for client-server communication - [stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#stdio) and [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#streamable-http). It also provides flexibility for different implementations and also permits custom transports. However, implementers must ensure the following which MiniMCP adhered to:

- All messages MUST use JSON-RPC 2.0 format and be UTF-8 encoded.
- Lifecycle requirements during both initialization and operation phases are met.
- Each message represents an individual request, notification, or response.

 MiniMCP makes use of the flexibility to provide a third HTTP transport.

### 1. Stdio Transport

The stdio transport implements the standard MCP communication mechanism over standard input/output streams, as defined in the [official specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#stdio). This transport enables bidirectional communication and is commonly employed for developing local MCP servers.

MiniMCP's stdio transport achieves full specification compliance with the following implementation:

#### Stdio Core Requirements

**Fully Supported:**

- **UTF-8 Encoding**: All JSON-RPC messages MUST be UTF-8 encoded ✅
- **Stdin/Stdout Communication**: Server reads from stdin, writes to stdout ✅
- **Individual Messages**: Each message is a single JSON-RPC request, notification, or response ✅
- **Newline Delimited**: Messages are delimited by newlines ✅
- **No Embedded Newlines**: Messages MUST NOT contain embedded newlines ✅
- **Message Validation**: Only valid MCP messages written to stdout ✅

#### Message Format

Per the specification, MiniMCP stdio transport ensures:

- Messages are newline-delimited (`\n` separator)
- Each line represents exactly one JSON-RPC message
- No embedded newlines (`\n` or `\r`) within message content
- UTF-8 encoding throughout the transport layer
- Line buffering for immediate message delivery

#### Validation

MiniMCP stdio transport validates all outgoing messages:

- **Embedded Newline Check**: Raises `ValueError` if message contains `\n` or `\r` characters
- **Message Type Check**: Ensures only `Message` or `NoMessage` types are processed
- **Encoding Validation**: UTF-8 encoding enforced via `TextIOWrapper`

#### Logging Requirements

Per the specification: "The server MAY write UTF-8 strings to its standard error (stderr) for logging purposes."

MiniMCP follows this requirement:

- All logging MUST be configured to write to stderr, not stdout
- Example servers demonstrate proper logging configuration
- Documentation explicitly warns developers about this requirement
- Improper logging configuration would violate the stdout message constraint

**Example logging configuration:**

```python
import sys
import logging

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[logging.StreamHandler(sys.stderr)]
)
```

#### Stdio Implementation Details

- **Subprocess Model**: Client launches server as subprocess
- **Bidirectional Communication**: Full duplex communication over stdin/stdout
- **Concurrent Handling**: Messages processed concurrently via anyio task groups
- **Backpressure**: anyio.wrap_file naturally applies backpressure
- **Error Handling**: Exceptions from handlers trigger transport shutdown

#### Stdin Behavior

- Reads JSON-RPC messages line-by-line from standard input
- Strips whitespace and skips empty lines
- Each non-empty line spawned as concurrent task
- Async iteration over stdin stream

#### Stdout Behavior

- Writes JSON-RPC messages to standard output
- Appends newline delimiter to each message
- Line buffering enabled for immediate delivery
- Validates no embedded newlines before writing
- Handles `NoMessage` enum for notification responses

#### Stdio - Security Considerations

MiniMCP stdio transport implements security best practices:

- Message validation before writing to stdout ✅
- Proper stream isolation (stdout for messages, stderr for logs) ✅
- No user input written directly to stdout without validation ✅
- Error messages sanitized and logged to stderr ✅

#### Stdio Compliance Summary

**Compliance: 100%** ✅

MiniMCP's stdio transport achieves full specification compliance with all requirements:

- ✅ UTF-8 encoded messages
- ✅ Newline-delimited messages
- ✅ No embedded newlines (validated)
- ✅ Stdin/stdout communication model
- ✅ Individual JSON-RPC messages
- ✅ Proper logging to stderr (documented)
- ✅ Concurrent message handling
- ✅ Line buffering for immediate delivery

The implementation includes comprehensive unit tests covering all specification requirements, including edge cases for embedded newline validation.

### 2. HTTP Transport

HTTP is a subset of Streamable HTTP and doesn't provide bidirectional communication. But on the hind side, just like in the above integration example, it can be technically added as a restful API end point in any Python application for developing remote MCP servers.

- The transport SHOULD check the accept header, content type, protocol version, and request body
- Every message sent from the client MUST be a new HTTP POST request to the MCP endpoint.
- The body of the POST request MUST be a single JSON-RPC request or notification.
- If the input is a request - The server MUST return Content-Type: application/json, to return one response JSON object.
- If the input is a notification - If the server accepts, the server MUST return HTTP status code 202 Accepted with no body.
- If the server cannot accept, it MUST return an HTTP error status code (e.g., 400 Bad Request). The HTTP response body MAY comprise a JSON-RPC error response that has no id.
- Multiple POST requests must be served concurrently by the server.

### 3. Smart Streamable HTTP Transport

MiniMCP comes with a smart Streamable HTTP implementation. It keeps track of the usage pattern and sends back a normal JSON HTTP response if the handler just returns a response. In other words, the event stream is used only if a notification needs to be sent from the server to the client. For simplicity it uses polling to keep the stream open, and fully resumable Streamable HTTP can be supported in the future.

- The transport SHOULD check the accept header, content type, protocol version, and request body
- Every message sent from the client MUST be a new HTTP POST request to the MCP endpoint.
- The body of the POST request MUST be a single JSON-RPC request or notification.
- If the input is a request:
  - To return one response JSON object - The server MUST return Content-Type: application/json.
  - To return notifications followed by a response JSON object - The server MUST return an SSE stream with Content-Type: text/event-stream.
  - The SSE stream SHOULD eventually include a JSON-RPC response for the JSON-RPC request sent in the POST body.
- If the input is a notification - If the server accepts, the server MUST return HTTP status code 202 Accepted with no body.
- If the server cannot accept, it MUST return an HTTP error status code (e.g., 400 Bad Request). The HTTP response body MAY comprise a JSON-RPC error response that has no id.
- Multiple POST requests must be served concurrently by the server.
