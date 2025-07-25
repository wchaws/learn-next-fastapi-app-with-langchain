import uuid
import requests
from typing import Annotated
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from strands import Agent, tool
from strands.session.file_session_manager import FileSessionManager
from strands_tools import calculator

from .utils.schemas import (
    ChatRequest,
    format_finish_message,
    format_finish_step,
    format_start_step,
    format_text_part,
    format_tool_call,
    format_tool_call_delta,
    format_tool_call_streaming_start,
    format_tool_result,
)


def p(*msg):
    print(*msg, flush=True)


load_dotenv(".env.local")

app = FastAPI()


@tool
def get_current_weather(
    latitude: Annotated[float, "The latitude of the location"],
    longitude: Annotated[float, "The longitude of the location"],
):
    """Get the current weather in a given location latitude and longitude"""

    res = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m&timezone=auto"
    )

    return res.json()


@tool
def add(a: int, b: int) -> int:
    """Adds a and b."""
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiplies a and b."""
    return a * b


# Async function that iterates over streamed agent events
from strands.handlers.callback_handler import PrintingCallbackHandler


class AgentStreamer:
    def __init__(self, agent: Agent) -> None:
        """Initialize handler."""
        self.agent = agent
        self.tool_count = 0
        self.previous_tool_use = None

    async def __call__(self, msg: str):
        """Stream text output and tool invocations to stdout.

        Args:
            msg: The message to process.
        """
        agent_stream = self.agent.stream_async(msg)

        async for event in agent_stream:
            p(event)

            reasoningText = event.get("reasoningText", False)
            data = event.get("data", "")
            complete = event.get("complete", False)
            current_tool_use = event.get("current_tool_use", {})
            tool_result = event.get("tool_result")

            if data:
                yield format_text_part(data)

            if current_tool_use and current_tool_use.get("name"):
                tool_id = current_tool_use.get("toolUseId")
                tool_name = current_tool_use.get("name", "Unknown tool")

                if self.previous_tool_use != current_tool_use:
                    self.previous_tool_use = current_tool_use

                    yield format_tool_call_streaming_start(tool_id, tool_name)

                args_delta = event["delta"]["toolUse"]["input"]
                if args_delta:
                    yield format_tool_call_delta(tool_id, args_delta)

            message = event.get("message")
            if message:
                if message["role"] == "user":
                    content = message["content"]
                    for each in content:
                        tool_result_dict = each.get("toolResult")
                        if tool_result_dict:
                            tool_id = tool_result_dict.get("toolUseId")
                            result = tool_result_dict.get("content", [{"text": ""}])[0][
                                "text"
                            ]

                            yield format_tool_result(tool_id, result)

            evt = event.get("event", {})

            if "messageStart" in evt:
                yield format_start_step(str(uuid.uuid4()))

            if "messageStop" in evt:
                yield format_finish_step("stop", 100, 100)


@app.post("/api/chat")
def handle_chat_data(request: ChatRequest, protocol: str = Query("data")):
    chat_id = request.id
    messages = request.messages
    last_message = messages[-1]

    session_manager = FileSessionManager(
        session_id=chat_id,
        storage_dir=".agent-history",  # Optional, defaults to a temp directory
    )

    agent = Agent(
        model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        tools=[get_current_weather, add, multiply],
        session_manager=session_manager,
        callback_handler=None,  # Disable default callback handler
    )

    streamer = AgentStreamer(agent)

    response = StreamingResponse(streamer(last_message.content))

    response.headers["x-vercel-ai-data-stream"] = "v1"
    return response
