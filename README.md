# Winnipeg City MCP Server

A powerful [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that enables AI assistants to access real-time Winnipeg Transit data and 311 City Services information. This server allows AI models like Claude to help users plan trips, check bus arrivals, find stops, and explore city service reports.

## Features

- 🚌 **Real-time Transit Information**: Get live bus arrival times and route status
- 🗺️ **Trip Planning**: Plan single trips or multi-stop journeys with optimized routes
- 📍 **Location Search**: Find bus stops near any location
- 🏙️ **311 City Services**: Search for reported issues and explore neighborhoods
- ⏱️ **Time-Aware Routing**: Get accurate transit schedules based on actual timetables

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
- Python 3.12+
- Winnipeg Transit API key (see setup instructions below)

## Setup

### 1. Get a Winnipeg Transit API Key

To use the transit features, you'll need a free API key from Winnipeg Transit:

1. Visit the [Winnipeg Transit API Registration](https://api.winnipegtransit.com/) page
2. Sign up for a free developer account
3. Once approved, you'll receive your API key via email

### 2. Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API key:
   ```bash
   TRANSIT_API_KEY=your_actual_api_key_here
   ```

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

## Contributing

Contributions are welcome! Feel free to:
- Report bugs or suggest features by opening an issue
- Submit pull requests with improvements
- Improve documentation

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Winnipeg Transit](https://winnipegtransit.com/) for providing the transit API
- [City of Winnipeg Open Data](https://data.winnipeg.ca/) for 311 services data
- [Model Context Protocol](https://modelcontextprotocol.io) for the MCP framework
