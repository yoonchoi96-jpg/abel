#!/usr/bin/env python3
import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main(url: str, call_tool: bool = False):
    print(f"Connecting: {url}")
    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("Initializing...")
            init = await session.initialize()
            print("SERVER:", init.server_info)
            print("PROTOCOL:", init.protocol_version)

            result = await session.list_tools()
            tools = result.tools

            print("TOOLS:")
            for tool in tools:
                print(f"  - {tool.name}")
                if tool.name == "generate_lesson_audio":
                    print("    description:", tool.description)
                    print("    input_schema:", tool.input_schema)

            names = [t.name for t in tools]
            if "generate_lesson_audio" not in names:
                raise SystemExit(
                    "FAIL: generate_lesson_audio is NOT exposed by the live MCP server."
                )

            print("PASS: generate_lesson_audio is exposed by the live MCP server.")

            if call_tool:
                print("\nCALLING generate_lesson_audio...")
                result = await session.call_tool(
                    "generate_lesson_audio",
                    {
                        "text": "你好，这是 Abel MCP 的实际工具调用测试。",
                        "title": "Abel MCP Smoke Test",
                        "level": "HSK6",
                        "topic": "MCP smoke test",
                    },
                )
                print("TOOL RESULT:", result)
                if getattr(result, "is_error", False):
                    raise SystemExit("FAIL: generate_lesson_audio returned an MCP tool error.")
                print("PASS: generate_lesson_audio executed successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python3 scripts/mcp_smoke_test.py https://HOST/mcp"
        )
    url = sys.argv[1]\n    call_tool = "--call" in sys.argv[2:]\n    asyncio.run(main(url, call_tool))
