#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main(url: str, call_tool: bool = False):
    print(f"Connecting: {url}")
    token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(headers=headers, timeout=120) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _get_session_id):
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
                        "questions_json": '[{"number":1,"part":"listening","stem":"测试","options":["A甲","B乙","C丙","D丁"],"answer":"A"}]',
                        "expected_total": 1
                    },
                )
                if getattr(qa_result, "is_error", False):
                    raise SystemExit("FAIL: evaluate_hsk_content returned an MCP tool error.")
                qa_payload = json.loads(qa_result.content[0].text)
                if qa_payload.get("tool_status") != "success":
                    raise SystemExit("FAIL: evaluate_hsk_content did not report tool_status=success.")
                if qa_payload.get("status") != "PASS":
                    raise SystemExit(
                        "FAIL: evaluate_hsk_content deterministic status was "
                        + str(qa_payload.get("status"))
                    )
                print("PASS: evaluate_hsk_content executed and preserved deterministic QA status.")

                deterministic_payload = {
                    key: value
                    for key, value in qa_payload.items()
                    if key not in {"semantic_review_prompt", "tool_status"}
                }
                gate_result = await session.call_tool(
                    "finalize_hsk_review",
                    {
                        "deterministic_report_json": json.dumps(deterministic_payload, ensure_ascii=False),
                    },
                )
                if getattr(gate_result, "is_error", False):
                    raise SystemExit("FAIL: finalize_hsk_review returned an MCP tool error.")
                gate_payload = json.loads(gate_result.content[0].text)
                if gate_payload.get("status") != "success":
                    raise SystemExit("FAIL: finalize_hsk_review did not report status=success.")
                if gate_payload.get("review", {}).get("gate") != "REVIEW":
                    raise SystemExit("FAIL: finalize_hsk_review incorrectly released without semantic review.")
                print("PASS: finalize_hsk_review executed and blocked missing semantic review.")

                if call_tool:
                    print("\nCALLING generate_lesson_audio...")
                    audio_result = await session.call_tool(
                        "generate_lesson_audio",
                        {
                            "text": "你好，这是 Abel MCP 的实际 Gemini TTS 工具调用测试。",
                            "title": "Abel MCP Smoke Test",
                            "level": "HSK6",
                            "topic": "MCP smoke test",
                        },
                    )
                    print("TOOL RESULT:", audio_result)
                    if getattr(audio_result, "is_error", False):
                        raise SystemExit("FAIL: generate_lesson_audio returned an MCP tool error.")
                    if not audio_result.content or not getattr(audio_result.content[0], "text", ""):
                        raise SystemExit("FAIL: generate_lesson_audio returned no structured payload.")
                    audio_payload = json.loads(audio_result.content[0].text)
                    if audio_payload.get("status") != "success":
                        raise SystemExit(
                            "FAIL: generate_lesson_audio status was "
                            + str(audio_payload.get("status"))
                            + ": "
                            + str(audio_payload.get("message", ""))
                        )
                    if audio_payload.get("provider") != "gemini":
                        raise SystemExit(
                            "FAIL: generate_lesson_audio provider was "
                            + str(audio_payload.get("provider"))
                        )
                    if not audio_payload.get("fileId") or not audio_payload.get("fileUrl"):
                        raise SystemExit("FAIL: Gemini TTS succeeded but Drive file metadata is missing.")
                    print(
                        "PASS: real Gemini TTS generated an MP3 and saved it to Drive. "
                        f"fileId={audio_payload['fileId']} provider={audio_payload['provider']}"
                    )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            "Usage: python3 scripts/mcp_smoke_test.py https://HOST/mcp [--call]"
        )
    url = sys.argv[1]
    call_tool = "--call" in sys.argv[2:]
    asyncio.run(main(url, call_tool))
