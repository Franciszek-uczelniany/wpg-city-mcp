# Winnipeg City MCP Server

An MCP (Model Context Protocol) server that provides tools for accessing Winnipeg Transit data and 311 City Services information.

## Tools Included

### Transit
- `get_bus_arrivals`: Get real-time bus arrivals for a specific stop
- `get_commute_status`: Check status of specific bus routes
- `find_stops_near`: Find bus stops near a location
- `plan_trip`: search for a trip from an origin to a destination
- `plan_journey`: Plan a multi-stop journey

### City Services
- `search_311_issues`: Search for reported 311 issues
- `list_neighborhoods`: List Winnipeg neighborhoods

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (recommended for running the script)
- Python 3.10+

## How to Run

You can run the server directly using `uv`:

```bash
uv run server.py
```

## Connecting to Claude Desktop

To use this MCP server with the Claude Desktop app:

1. Open your Claude Desktop configuration file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the following configuration (replace `/ABSOLUTE/PATH/TO/` with the actual path to this repository):

```json
{
  "mcpServers": {
    "winnipeg-city": {
      "command": "uv",
      "args": [
        "run",
        "/ABSOLUTE/PATH/TO/wpg-city-mcp/server.py"
      ]
    }
  }
}
```

3. Restart Claude Desktop.

## Debugging with MCP Inspector

You can test and debug the server using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector uv run server.py
```

This will start the Inspector in your browser, allowing you to manually call tools and verify the server's behavior.

