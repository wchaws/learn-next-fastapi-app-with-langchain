import os
import json
from typing import List
from langchain_aws import ChatBedrock, ChatBedrockConverse
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from openai import OpenAI
from langchain_core.messages import AIMessageChunk
from .utils.prompt import ClientMessage, convert_to_openai_messages
from .utils.tools import add, get_current_weather, multiply
from langchain_community.adapters.openai import (
    convert_openai_messages as openai_2_langchain,
)
from langchain_core.messages.utils import (
    convert_to_openai_messages as langchain_2_openai,
)


load_dotenv(".env.local")

app = FastAPI()

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_API_BASE_URL")
)

llm = ChatBedrockConverse(
    model="anthropic.claude-3-5-sonnet-20241022-v2:0",
    # model="anthropic.claude-3-5-sonnet-20240620-v1:0",
    # model="anthropic.claude-3-sonnet-20240229-v1:0",
    # model="anthropic.claude-3-haiku-20240307-v1:0",
    temperature=0.1,
)


class Request(BaseModel):
    messages: List[ClientMessage]


available_tools = {
    "get_current_weather": get_current_weather,
    "add": add,
    "multiply": multiply,
}

llm = llm.bind_tools([add, multiply, get_current_weather])

def stream_text(messages: List[ClientMessage], protocol: str = 'data'):
    stream = client.chat.completions.create(
        messages=messages,
        model="sonnet-3.5-v2",
        stream=True,
        tools=[{
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location", "unit"],
                },
            },
        }]
    )

    # When protocol is set to "text", you will send a stream of plain text chunks
    # https://sdk.vercel.ai/docs/ai-sdk-ui/stream-protocol#text-stream-protocol

    if (protocol == 'text'):
        for chunk in stream:
            for choice in chunk.choices:
                if choice.finish_reason == "stop":
                    break
                else:
                    yield "{text}".format(text=choice.delta.content)

    # When protocol is set to "data", you will send a stream data part chunks
    # https://sdk.vercel.ai/docs/ai-sdk-ui/stream-protocol#data-stream-protocol

    elif (protocol == 'data'):
        draft_tool_calls = []
        draft_tool_calls_index = -1

        for chunk in stream:
            for choice in chunk.choices:
                if choice.finish_reason == "stop":
                    continue

                elif choice.finish_reason == "tool_calls":
                    for tool_call in draft_tool_calls:
                        yield '9:{{"toolCallId":"{id}","toolName":"{name}","args":{args}}}\n'.format(
                            id=tool_call["id"],
                            name=tool_call["name"],
                            args=tool_call["arguments"])

                    for tool_call in draft_tool_calls:
                        tool_result = available_tools[tool_call["name"]](
                            (tool_call["arguments"]))

                        yield 'a:{{"toolCallId":"{id}","toolName":"{name}","args":{args},"result":{result}}}\n'.format(
                            id=tool_call["id"],
                            name=tool_call["name"],
                            args=tool_call["arguments"],
                            result=json.dumps(tool_result))

                elif choice.delta.tool_calls:
                    for tool_call in choice.delta.tool_calls:
                        id = tool_call.id
                        name = tool_call.function.name
                        arguments = tool_call.function.arguments

                        if (id is not None):
                            draft_tool_calls_index += 1
                            draft_tool_calls.append(
                                {"id": id, "name": name, "arguments": ""})

                        else:
                            draft_tool_calls[draft_tool_calls_index]["arguments"] += arguments

                else:
                    yield '0:{text}\n'.format(text=json.dumps(choice.delta.content))

            if chunk.choices == []:
                usage = chunk.usage
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens

                yield 'd:{{"finishReason":"{reason}","usage":{{"promptTokens":{prompt},"completionTokens":{completion}}}}}\n'.format(
                    reason="tool-calls" if len(
                        draft_tool_calls) > 0 else "stop",
                    prompt=prompt_tokens,
                    completion=completion_tokens
                )

def p(*msg):
    print(*msg, flush=True)


def langchain_stream_text(messages: List[ClientMessage], protocol: str = 'data'):
    langchain_messages = openai_2_langchain(messages)
    stream = llm.stream(langchain_messages)

    if (protocol == 'text'):
        for chunk in stream:
            yield "{text}".format(text=chunk.text())
        
    
    elif (protocol == 'data'):
        gathered = AIMessageChunk(content=[])
        for chunk in stream:
            gathered += chunk

            for content in chunk.content:
                p(content)
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "text":
                    yield '0:{text}\n'.format(text=json.dumps(content["text"]))
                elif content.get("type") == "tool_use":
                    pass
        
        for tool_call in gathered.tool_calls:
            p(tool_call)
            
            yield "9:" + json.dumps({
                "toolCallId": tool_call["id"],
                "toolName": tool_call["name"],
                "args": tool_call["args"],
            }) + "\n"


            if func := available_tools.get(tool_call["name"]):
                result = func.invoke(input=tool_call["args"])
                
                yield "a:" + json.dumps({
                    "toolCallId": tool_call["id"],
                    "toolName": tool_call["name"],
                    "args": tool_call["args"],
                    "result": result
                }) + "\n"

        
        p(gathered)

        if stop_reason := gathered.response_metadata.get("stopReason"):
            stop_reason_map = {
                "tool_use": "tool-calls",
                "end_turn": "stop",
            }


            yield "d:" + json.dumps({
                "finishReason": stop_reason_map.get(stop_reason, "other"),
                "usage": {
                    "promptTokens": gathered.usage_metadata["input_tokens"],
                    "completionTokens": gathered.usage_metadata["output_tokens"]
                }
            }) + "\n"



@app.post("/api/chat")
async def handle_chat_data(request: Request, protocol: str = Query("data")):
    messages = request.messages
    openai_messages = convert_to_openai_messages(messages)

    response = StreamingResponse(langchain_stream_text(openai_messages, protocol))
    # response = StreamingResponse(stream_text(openai_messages, protocol))
    response.headers["x-vercel-ai-data-stream"] = "v1"
    return response
