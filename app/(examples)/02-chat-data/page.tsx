"use client";

import { Card } from "@/app/components";
import { Message, useChat } from "@ai-sdk/react";
import { GeistMono } from "geist/font/mono";
import { useEffect, useState } from "react";

export default function Page() {
  const [initialMessages, setInitialMessages] = useState<Message[]>([]);

  const {
    messages,
    input,
    handleSubmit,
    handleInputChange,
    status,
    setMessages,
    data,
    error,
  } = useChat({
    streamProtocol: "data",
    maxSteps: 0,
    sendExtraMessageFields: true,

    initialMessages,
    // onFinish: () => {
    //   setMessages((messages) => {
    //     console.log("Chat finished", messages);
    //     return messages;
    //   });
    // },
  });

  useEffect(() => {
    console.log("On message changes", messages);
  }, [messages]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-2 p-4">
        {messages.map((message) => (
          <div key={message.id} className="flex flex-row gap-2">
            <div className="flex-shrink-0 w-24 text-zinc-500">{`${message.role}: `}</div>

            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-2">
                {message.parts
                  .map((part, index) => {
                    const { type } = part;
                    if (type === "tool-invocation") {
                      const { toolInvocation } = part;
                      const { toolName, toolCallId, state, args, step } =
                        toolInvocation;

                      return (
                        <pre
                          key={toolCallId}
                          className={`${GeistMono.className} text-sm text-zinc-500 bg-zinc-100 p-3 rounded-lg`}
                        >
                          <b>STEP #{1 + (step || 0)}:</b>
                          <br />
                          {`${toolName}(${JSON.stringify(args, null, 2)})`}
                        </pre>
                      );
                    }

                    if (type === "text") {
                      return <pre key={index}>{part.text}</pre>;
                    }
                  })
                  .filter(Boolean)}
                {/* {message.toolInvocations?.map((toolInvocation) => (
                  <pre
                    key={toolInvocation.toolCallId}
                    className={`${GeistMono.className} text-sm text-zinc-500 bg-zinc-100 p-3 rounded-lg`}
                  >
                    {`${toolInvocation.toolName}(${JSON.stringify(
                      toolInvocation.args,
                      null,
                      2
                    )})`}
                  </pre>
                ))} */}
              </div>
            </div>
          </div>
        ))}
      </div>

      {messages.length === 0 && <Card type="chat-data" />}

      <form
        onSubmit={(e) => {
          handleSubmit(e, {
            data: { msg: "this is fake data" },
            body: { msg: "this is fake body" },
          });
        }}
        className="fixed bottom-0 flex flex-col w-full border-t"
      >
        <input
          value={input}
          placeholder="What's the weather in San Francisco?"
          onChange={handleInputChange}
          className="w-full p-4 bg-transparent outline-none"
          disabled={status !== "ready"}
        />

        <div>Status: {status}</div>
        <div>Error: {String(error)}</div>
      </form>
    </div>
  );
}
