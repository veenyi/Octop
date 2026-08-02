import { describe, expect, it } from "vitest";
import type { ChatMessage } from "../hooks/useChat";
import { groupConsecutiveAssistantMessages } from "./messageGrouping";

function msg(
  role: ChatMessage["role"],
  id: string,
  extra?: Partial<ChatMessage>,
): ChatMessage {
  return {
    id,
    role,
    content: extra?.content ?? "",
    status: "done",
    timestamp: Date.now(),
    ...extra,
  };
}

describe("groupConsecutiveAssistantMessages", () => {
  it("keeps tool-role rows inside the assistant turn", () => {
    const groups = groupConsecutiveAssistantMessages([
      msg("user", "u1", { content: "hi" }),
      msg("assistant", "a1", {
        toolData: { name: "read_file", arguments: "{}" },
      }),
      msg("tool", "t1", {
        toolData: { name: "read_file", output: "ok" },
      }),
      msg("assistant", "a2", {
        content: "done",
        contentBlocks: [{ type: "thinking", content: "…" }],
      }),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0].messages.map((m) => m.id)).toEqual(["u1"]);
    expect(groups[1].isGroup).toBe(true);
    expect(groups[1].messages.map((m) => m.id)).toEqual(["a1", "t1", "a2"]);
  });

  it("still splits on user messages", () => {
    const groups = groupConsecutiveAssistantMessages([
      msg("assistant", "a1", { content: "one" }),
      msg("user", "u1", { content: "again" }),
      msg("assistant", "a2", { content: "two" }),
    ]);
    expect(groups).toHaveLength(3);
    expect(groups[1].messages[0].id).toBe("u1");
  });
});
