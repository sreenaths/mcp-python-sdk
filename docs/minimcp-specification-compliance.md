# MiniMCP Specification Compliance

## Primitives
Primitives are the fundamental building blocks for adding context to language models via MCP. They enable rich interactions between clients, servers, and language models.

### 1. Prompts

### 2. Resources

Resources in MCP provide a standardized way for servers to expose data that provides context to language models. According to the [official specification](https://modelcontextprotocol.io/specification/2025-06-18/server/resources), each resource is uniquely identified by a URI and can represent files, database schemas, API responses, or any application-specific data. Resources are application-driven—host applications determine how to incorporate context based on their needs.

MiniMCP fully implements the core resource specification with the following compliance:

#### Core Protocol Messages

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

#### Annotations

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

#### Capabilities Declaration

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

#### Error Handling

MiniMCP follows the specification's error handling requirements:
- Resource not found: Error code `-32002` with appropriate message
- Internal errors: Error code `-32603`
- URI validation performed before resource operations
- Proper error messages with context (URI, resource name)

#### Security Considerations

Per the specification, MiniMCP:
- Validates all resource URIs before processing
- Encourages implementation-specific access controls for sensitive resources
- Properly encodes binary data (base64)
- Recommends permission checks before resource operations

**Compliance Summary:** MiniMCP achieves ~95% specification compliance for resources, with all mandatory features fully implemented. The missing features (subscriptions and list change notifications) are explicitly optional per the specification.

### 3. Tools

## Transport

The official MCP specification currently defines two standard transport mechanisms for client-server communication - [stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#stdio) and [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#streamable-http). It also provides flexibility for different implementations and also permits custom transports. However, implementers must ensure the following which MiniMCP adhered to:

- All messages MUST use JSON-RPC 2.0 format and be UTF-8 encoded.
- Lifecycle requirements during both initialization and operation phases are met.
- Each message represents an individual request, notification, or response.

 MiniMCP makes use of the flexibility to provide a third HTTP transport.

### 1. Stdio Transport

Consistent with the standard, stdio enables bidirectional communication and is commonly employed for developing local MCP servers.

- The server reads messages from its standard input (stdin) and sends messages to its standard output (stdout).
- Messages are delimited by newlines.
- Only valid MCP messages should be written into stdin and stdout.

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
