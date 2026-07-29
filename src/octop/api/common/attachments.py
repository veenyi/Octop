"""Chat attachment HTTP helpers — thin wrappers over :mod:`inbound_store`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

from octop.infra.gateway.media.attachment_hints import is_image_media_type
from octop.infra.gateway.media.inbound_store import InboundFile, write_inbound

if TYPE_CHECKING:
    from harness_agent.backends.workspace import BackendWorkspace

# 单文件上传上限：500MB（与 inbound_store.MAX_INBOUND_BYTES 保持一致；飞牛本地版放开限制）。
MAX_ATTACHMENT_BYTES = 500 * 1024 * 1024


@dataclass(frozen=True)
class StoredAttachment:
    filename: str
    media_type: str
    size: int
    data_path: str
    owner_id: int = 0


def _stored_from_inbound(inbound: InboundFile, *, owner_id: int = 0) -> StoredAttachment:
    return StoredAttachment(
        owner_id=owner_id,
        filename=inbound.filename,
        media_type=inbound.media_type,
        size=inbound.size,
        data_path=inbound.path,
    )


def dashboard_inbound_preview_url(
    agent_id: str,
    workspace_path: str,
    *,
    media_type: str = "",
) -> str:
    """JWT-protected preview/download URL for dashboard UI (not for LLM)."""
    rel = workspace_path.lstrip("/")
    aid = quote(agent_id, safe="")
    if is_image_media_type(media_type) or media_type.startswith("video/"):
        params = f"source={quote(rel, safe='')}"
        if media_type:
            params += f"&mime_type={quote(media_type, safe='')}"
        return f"/api/agents/{aid}/media/preview?{params}"
    return f"/api/agents/{aid}/workspace/download?path={quote(rel, safe='')}"


async def save_attachment(
    workspace: BackendWorkspace,
    *,
    owner_id: int,
    filename: str,
    media_type: str,
    data: bytes,
) -> StoredAttachment:
    del owner_id  # access control is JWT + agent scope at download time
    inbound = await write_inbound(
        workspace,
        data,
        filename=filename,
        media_type=media_type,
    )
    return _stored_from_inbound(inbound)
