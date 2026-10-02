#!/usr/bin/env python3
import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main(url: str):
    print(f"Connecting: {url}")
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("Initializing...")
            init = await session.initialize()
            print("SERVER:", init.serverInfo)
            print("PROTOCOL:", init.protocolVersion)

            result = await session.list_tools()
            tools = result.tools

            print("TOOLS:")
            for tool in tools:
                print(f"  - {tool.name}")
                if tool.name == "generate_lesson_audio":
                    print("    description:", tool.description)
                    print("    inputSchema:", tool.inputSchema)

            names = [t.name for t in tools]
            if "generate_lesson_audio" not in names:
                raise SystemExit(
                    "FAIL: generate_lesson_audio is NOT exposed by the live MCP server."
                )

            print("PASS: generate_lesson_audio is exposed by the live MCP server.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python3 scripts/mcp_smoke_test.py https://HOST/mcp"
        )
    asyncio.run(main(sys.argv[1]))
