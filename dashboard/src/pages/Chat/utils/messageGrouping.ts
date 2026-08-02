import type { ChatMessage } from "../hooks/useChat";

export interface MessageGroup {
  isGroup: boolean;
  messages: ChatMessage[];
}

/** Roles that belong to an assistant ReAct turn (must not split the group). */
function isAssistantTurnRole(role: string): boolean {
  return role === "assistant" || role === "tool";
}

/**
 * Group consecutive assistant-turn messages for unified turn rendering.
 *
 * History loads often keep unmatched ``tool``-role rows between AI steps;
 * treating them as turn breakers produced multiple process summaries for one
 * user round-trip. Keep ``tool`` inside the assistant group.
 */
export function groupConsecutiveAssistantMessages(
  messages: ChatMessage[],
): MessageGroup[] {
  const groups: MessageGroup[] = [];
  let currentGroup: ChatMessage[] = [];

  for (const msg of messages) {
    if (isAssistantTurnRole(msg.role)) {
      currentGroup.push(msg);
    } else {
      if (currentGroup.length > 0) {
        groups.push({ isGroup: true, messages: currentGroup });
        currentGroup = [];
      }
      groups.push({ isGroup: false, messages: [msg] });
    }
  }

  if (currentGroup.length > 0) {
    groups.push({ isGroup: true, messages: currentGroup });
  }

  return groups;
}
