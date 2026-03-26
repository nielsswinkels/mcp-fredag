#!/usr/bin/env python3
"""
MCP Server: Är det fredag?
A simple MCP server that tells you if it's Friday.

Supports two transport modes:
  - stdio (default): for Claude Desktop local use
  - sse: for hosting (Coolify, etc.) — set TRANSPORT=sse
"""

import asyncio
import os
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from mcp.server import Server
from mcp.types import Tool, TextContent

# Create the MCP server
server = Server("ardetfredag")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="ar_det_fredag",
            description="Checks if it's Friday in Sweden. Returns JA or NEJ.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name != "ar_det_fredag":
        raise ValueError(f"Unknown tool: {name}")

    # Check Swedish time
    sweden_tz = ZoneInfo("Europe/Stockholm")
    now = datetime.now(sweden_tz)
    is_friday = now.weekday() == 4  # Monday = 0, Friday = 4

    # Try to fetch from the actual site for fun
    site_says = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://www.xn--rdetfredag-p5a.se/")
            if response.status_code == 200:
                html = response.text.upper()
                if "JA" in html:
                    site_says = "JA"
                elif "NEJ" in html:
                    site_says = "NEJ"
    except Exception:
        pass  # Site unreachable, we'll use local calculation

    # Build response
    answer = "JA! 🎉" if is_friday else "NEJ 😢"
    day_name = now.strftime("%A")

    result = f"Är det fredag? {answer}\n"
    result += f"(Det är {day_name} i Sverige, {now.strftime('%Y-%m-%d %H:%M')})"

    if site_says:
        result += f"\n\närdetfredag.se säger också: {site_says}"

    return [TextContent(type="text", text=result)]

if __name__ == "__main__":
    transport = os.environ.get("TRANSPORT", "stdio")

    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        import uvicorn

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server.run(
                    streams[0], streams[1], server.create_initialization_options()
                )

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ]
        )

        port = int(os.environ.get("PORT", 8000))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        from mcp.server.stdio import stdio_server

        async def main():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream, write_stream, server.create_initialization_options()
                )

        asyncio.run(main())
