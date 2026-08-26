import type { ChatAttachment } from "../hooks/sseHelpers";

export const ACCEPTED_MIME_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/gif",
  "image/webp",
  "application/pdf",
  "text/plain",
  "text/markdown",
  "application/json",
  "text/csv",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/zip",
]);

export const ACCEPTED_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".pdf",
  ".txt",
  ".md",
  ".markdown",
  ".json",
  ".csv",
  ".docx",
  ".xlsx",
  ".pptx",
  ".zip",
]);

export const CHAT_ACCEPT_ATTR = ""; // 放开类型限制：文件选择器不再过滤，接受任意类型

export const CHAT_MAX_ATTACHMENT_BYTES = 500 * 1024 * 1024; // 单文件上限 500MB

const THINKING_TAG_RE = /<think>[\s\S]*?<\/redacted_thinking>\s*/gi;

const IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|bmp|svg)$/i;

export function stripThinkingTags(text: string): string {
  return text.replace(THINKING_TAG_RE, "").trim();
}

export function isImageMediaType(mime?: string): boolean {
  return Boolean(mime?.startsWith("image/"));
}

export function inferKindFromNameAndMime(
  mediaType?: string,
  filename?: string,
  kind?: ChatAttachment["kind"],
): ChatAttachment["kind"] {
  if (kind === "image" || kind === "video" || kind === "audio") {
    return kind;
  }
  const mime = (mediaType || "").toLowerCase();
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  const fromName = filename
    ? getMediaKind(filename.split("?")[0] || filename)
    : null;
  return fromName ?? "file";
}

export function isImageFilename(name?: string): boolean {
  if (!name) return false;
  return IMAGE_EXT_RE.test(name.split("?")[0]);
}

/** Vision model input — not a workspace path hint for tools. */
export function isImageAttachment(attachment: {
  kind?: ChatAttachment["kind"];
  mediaType?: string;
  filename?: string;
}): boolean {
  if (attachment.kind === "image") return true;
  if (isImageMediaType(attachment.mediaType)) return true;
  return isImageFilename(attachment.filename);
}

export function inferAttachmentKind(
  file: File,
  serverMediaType: string,
): ChatAttachment["kind"] {
  return isImageAttachment({
    mediaType: serverMediaType || file.type,
    filename: file.name,
  })
    ? "image"
    : "file";
}

export function isAcceptedChatFile(_file: File): boolean {
  // 上传类型限制已放开：接受任意文件类型，不再拦截。
  return true;
}

/** Vision block — backend materializes to ``image_url`` base64 for the LLM. */
export function toImageContentBlock(
  attachment: ChatAttachment,
): Record<string, unknown> {
  return {
    type: "image",
    source: {
      type: "url",
      url: attachment.url,
      ...(attachment.mediaType ? { media_type: attachment.mediaType } : {}),
    },
    preview_url: attachment.url,
    ...(attachment.workspacePath
      ? { workspace_path: attachment.workspacePath }
      : {}),
    ...(attachment.filename ? { filename: attachment.filename } : {}),
  };
}

/** Non-image block — backend converts to a workspace path hint for agent tools. */
export function toFileContentBlock(
  attachment: ChatAttachment,
): Record<string, unknown> {
  return {
    type: "file",
    filename: attachment.filename || "attachment",
    ...(attachment.mediaType ? { media_type: attachment.mediaType } : {}),
    ...(attachment.workspacePath
      ? { workspace_path: attachment.workspacePath }
      : {}),
  };
}

/**
 * Build OpenAI-style user content for a dashboard turn.
 * Images → vision blocks; other files → ``type: file`` (path hints applied server-side).
 */
export function buildUserMessageContent(
  text: string,
  attachments?: ChatAttachment[],
): string | Array<Record<string, unknown>> {
  const blocks: Array<Record<string, unknown>> = [];
  const trimmed = text.trim();

  if (trimmed) {
    blocks.push({ type: "text", text: trimmed });
  }

  for (const attachment of attachments ?? []) {
    if (isImageAttachment(attachment)) {
      blocks.push(toImageContentBlock(attachment));
    } else {
      blocks.push(toFileContentBlock(attachment));
    }
  }

  if (blocks.length === 0) return "";
  if (blocks.length === 1 && blocks[0].type === "text") {
    return String(blocks[0].text ?? "");
  }
  return blocks;
}
