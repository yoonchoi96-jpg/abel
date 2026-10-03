#!/usr/bin/env python3
import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main(url: str, call_tool: bool = False):
    print(f"Connecting: {url}")
    async with streamable_http_client(url) as (read_stream, write_stream, _get_session_id):
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
                if tool.name in {"generate_lesson_audio", "evaluate_hsk_content", "finalize_hsk_review"}:
                    print("    description:", tool.description)
                    print("    input_schema:", tool.inputSchema)

            names = [t.name for t in tools]
            required = {"generate_lesson_audio", "evaluate_hsk_content", "finalize_hsk_review"}
            missing = required.difference(names)
            if missing:
                raise SystemExit(
                    "FAIL: required Abel MCP tools are missing: " + ", ".join(sorted(missing))
                )

            print("PASS: audio + HSK evaluation + final-gate tools are exposed by the live MCP server.")

            qa_result = await session.call_tool(
                "evaluate_hsk_content",
                {
                    "questions_json": '[{"number":1,"part":"listening","stem":"测试","options":["A甲","B乙","C丙","D丁"],"answer":"A"}]'
                },
            )
            if getattr(qa_result, "is_error", False):
                raise SystemExit("FAIL: evaluate_hsk_content returned an MCP tool error.")
            print("PASS: evaluate_hsk_content executed successfully.")

            gate_result = await session.call_tool(
                "finalize_hsk_review",
                {
                    "deterministic_report_json": '{"status":"PASS","score":100}',
                },
            )
            if getattr(gate_result, "is_error", False):
                raise SystemExit("FAIL: finalize_hsk_review returned an MCP tool error.")
            print("PASS: finalize_hsk_review executed successfully.")

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
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            "Usage: python3 scripts/mcp_smoke_test.py https://HOST/mcp [--call]"
        )
    url = sys.argv[1]
    call_tool = "--call" in sys.argv[2:]
    asyncio.run(main(url, call_tool))
