#!/usr/bin/env python3
"""Replay canned agent-runtime SSE traces and print timing stats."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from contextlib import asynccontextmanager

from aiohttp import web


class Bridge:
    def __init__(self):
        self.events = []

    def emit_event(self, event_json: str):
        self.events.append(json.loads(event_json))

    async def invoke_tool(self, tool_call_json: str) -> str:
        payload = json.loads(tool_call_json)
        return json.dumps(
            {
                "tool_call_id": payload["tool_call_id"],
                "client_id": "client",
                "tool_name": "tool",
                "service_name": "Mock Service",
                "success": True,
                "tool_response": json.dumps({"ok": True}),
                "error_message": None,
            }
        )


def build_request(base_url: str, *, tools: list[dict] | None = None) -> str:
    return json.dumps(
        {
            "request_id": "benchmark-request",
            "session_id": "benchmark-session",
            "query": "hello",
            "max_steps": 4,
            "language": "UserLanguage.ENGLISH",
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hello"},
            ],
            "tools": tools or [],
            "planning_model_config": {
                "base_url": base_url,
                "api_key": "token",
                "model_name": "demo-model",
            },
        },
        ensure_ascii=False,
    )


def build_scenario(name: str) -> tuple[str, list[dict], list[list[dict]]]:
    if name == "content":
        return (
            "nlp",
            [],
            [
                [
                    {"choices": [{"delta": {"content": "Hello "}, "finish_reason": None}]},
                    {"choices": [{"delta": {"content": "world"}, "finish_reason": "stop"}]},
                ]
            ],
        )

    if name == "tool_loop":
        tool_name = "client___tool"
        return (
            "dynamic_execute",
            [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": "Mock tool",
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                        },
                    },
                }
            ],
            [
                [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_0",
                                            "function": {
                                                "name": tool_name,
                                                "arguments": "{\"city\":\"Paris\"}",
                                            },
                                        }
                                    ]
                                },
                                "finish_reason": "tool_calls",
                            }
                        ]
                    }
                ],
                [
                    {
                        "choices": [
                            {"delta": {"content": "Tool finished"}, "finish_reason": "stop"}
                        ]
                    }
                ],
            ],
        )

    raise ValueError(f"Unsupported scenario: {name}")


@asynccontextmanager
async def serve_sse(chunks_by_request: list[list[dict]]):
    app = web.Application()
    state = {"requests": []}

    async def handle(request):
        payload = await request.json()
        state["requests"].append(payload)
        chunk_index = len(state["requests"]) - 1
        chunks = chunks_by_request[chunk_index]

        response = web.StreamResponse(
            status=200,
            headers={"Content-Type": "text/event-stream"},
        )
        await response.prepare(request)
        for chunk in chunks:
            await response.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
        await response.write(b"data: [DONE]\n\n")
        await response.write_eof()
        return response

    app.router.add_post("/chat/completions", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", state
    finally:
        await runner.cleanup()


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


async def run_benchmark(scenario: str, iterations: int, warmup: int) -> None:
    try:
        import miloco_agent_runtime
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "miloco_agent_runtime is not installed. Build it first with "
            "`uvx maturin develop --manifest-path native/miloco-agent-runtime/Cargo.toml`."
        ) from exc

    request_kind, tools, per_run_requests = build_scenario(scenario)
    total_runs = warmup + iterations
    chunks_by_request = per_run_requests * total_runs
    runtime = miloco_agent_runtime.AgentRuntime()
    samples_ms = []

    async with serve_sse(chunks_by_request) as (base_url, state):
        request_json = build_request(base_url, tools=tools)

        for run_index in range(total_runs):
            bridge = Bridge()
            started_at = time.perf_counter()
            if request_kind == "dynamic_execute":
                await runtime.run_dynamic_execute(request_json, bridge)
            else:
                await runtime.run_nlp_request(request_json, bridge)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            if run_index >= warmup:
                samples_ms.append(elapsed_ms)

    total_requests = len(state["requests"])
    print(
        json.dumps(
            {
                "scenario": scenario,
                "iterations": iterations,
                "warmup": warmup,
                "llm_requests": total_requests,
                "mean_ms": round(statistics.mean(samples_ms), 3),
                "min_ms": round(min(samples_ms), 3),
                "p50_ms": round(percentile(samples_ms, 0.50), 3),
                "p95_ms": round(percentile(samples_ms, 0.95), 3),
                "max_ms": round(max(samples_ms), 3),
                "rps": round(iterations / (sum(samples_ms) / 1000), 3),
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=["content", "tool_loop"],
        default="tool_loop",
        help="Replay fixture to benchmark.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Measured iterations to execute.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Warmup iterations to discard.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    asyncio.run(run_benchmark(args.scenario, args.iterations, args.warmup))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
