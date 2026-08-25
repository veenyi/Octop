#!/usr/bin/env python3
"""Apply the QQ channel fixes to an installed harness_gateway package.

Idempotent: safe to run multiple times (checks for the marker before each
patch). Usage:
    python3 patch_harness_gateway.py <site-packages-dir>
e.g. python3 patch_harness_gateway.py fnos-native/app/site-packages

The patches are applied to
`<site-packages>/harness_gateway/channels/qq/channel.py`:

1. Refresh the OAuth access token before every send (fixes 401 after 2h).
2. Retry passive-reply expiry/limit (40034128/40034005) as a proactive msg.
3. Track the QQ passive-reply budget (max 5 per msg_id) and switch the
   remaining items to proactive messages.
4. Send media before text, abort the batch on the first send failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MARKER = "_consume_passive_budget"  # marker for patch group 1/3/4
_TOKEN_MARKER = "Refresh OAuth access token before sending"


def _patch(data: str, old: str, new: str) -> str:
    if old not in data:
        raise RuntimeError("pattern not found:\n" + old[:120])
    return data.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    sp = Path(sys.argv[1])
    target = sp / "harness_gateway" / "channels" / "qq" / "channel.py"
    if not target.is_file():
        print(f"[patch-hg] channel.py not found: {target}")
        return 1

    data = target.read_text(encoding="utf-8")
    changed = False

    # ---- Patch 1: refresh token before send (3 call sites) ----
    if _TOKEN_MARKER not in data:
        old = (
            '        http = await self._ensure_http()\n'
            '        headers = self._auth_headers()\n'
            '        headers["Content-Type"] = "application/json"'
        )
        new = (
            '        http = await self._ensure_http()\n'
            '        # Refresh OAuth access token before sending (expired token would 401)\n'
            '        await self._ensure_access_token()\n'
            '        headers = self._auth_headers()\n'
            '        headers["Content-Type"] = "application/json"'
        )
        # apply to every send path that matches (3 occurrences)
        n = data.count(old)
        if n == 0:
            print("[patch-hg] token-refresh pattern not found; skipped")
        else:
            data = data.replace(old, new)
            changed = True
            print(f"[patch-hg] token refresh applied to {n} send paths")
    else:
        print("[patch-hg] token refresh already applied")

    # ---- Patch 2: proactive retry on passive expiry ----
    if "retrying as proactive message" not in data:
        old = (
            '                if resp.status not in (200, 201, 202, 204):\n'
            '                    logger.error(\n'
            '                        "QQChannel send failed: status=%d url=%s payload_keys=%s body=%s",\n'
            '                        resp.status,\n'
            '                        url,\n'
            '                        list(payload.keys()),\n'
            '                        body[:500],\n'
            '                    )\n'
            '                    raise RuntimeError(f"QQChannel send failed: status={resp.status} body={body[:500]}")'
        )
        new = (
            '                if resp.status not in (200, 201, 202, 204):\n'
            '                    body = await resp.text()\n'
            '                    # Passive reply expired (40034128) or msg_id expired (40034005):\n'
            '                    # retry once as a proactive message so long-running replies\n'
            '                    # still reach the user (QQ allows proactive sends).\n'
            '                    if (\n'
            '                        resp.status == 400\n'
            '                        and payload.get("msg_id")\n'
            '                        and ("40034128" in body or "40034005" in body)\n'
            '                    ):\n'
            '                        logger.warning(\n'
            '                            "QQChannel passive reply expired (%s), retrying as proactive message",\n'
            '                            resp.status,\n'
            '                        )\n'
            '                        payload.pop("msg_id", None)\n'
            '                        payload.pop("msg_seq", None)\n'
            '                        async with http.post(url, headers=headers, json=payload) as resp2:\n'
            '                            body2 = await resp2.text()\n'
            '                            if resp2.status in (200, 201, 202, 204):\n'
            '                                logger.debug("QQChannel proactive message sent: endpoint=%s", endpoint)\n'
            '                                return\n'
            '                            logger.error(\n'
            '                                "QQChannel proactive send failed: status=%d body=%s",\n'
            '                                resp2.status,\n'
            '                                body2[:300],\n'
            '                            )\n'
            '                            raise RuntimeError(f"QQChannel send failed: status={resp2.status} body={body2[:500]}")\n'
            '                    logger.error(\n'
            '                        "QQChannel send failed: status=%d url=%s payload_keys=%s body=%s",\n'
            '                        resp.status,\n'
            '                        url,\n'
            '                        list(payload.keys()),\n'
            '                        body[:500],\n'
            '                    )\n'
            '                    raise RuntimeError(f"QQChannel send failed: status={resp.status} body={body[:500]}")'
        )
        data = _patch(data, old, new)
        changed = True
        print("[patch-hg] proactive retry applied")
    else:
        print("[patch-hg] proactive retry already applied")

    # ---- Patch 3: passive reply budget counter ----
    if _MARKER not in data:
        old = (
            '_msg_seq: dict[str, int] = {}\n'
            '_msg_seq_lock = threading.Lock()'
        )
        new = (
            '_msg_seq: dict[str, int] = {}\n'
            '_msg_seq_lock = threading.Lock()\n'
            '\n'
            '# QQ 官方被动回复限制：同一被动消息（msg_id）最多回复 5 次（超限报 40034128）。\n'
            '# 逐条发送的回复（文本+图片）共用该预算；超限后自动转主动消息补发。\n'
            '_QQ_PASSIVE_REPLY_LIMIT = 5\n'
            '_passive_reply_count: dict[str, int] = {}\n'
            '_passive_reply_lock = threading.Lock()\n'
            '\n'
            '\n'
            'def _consume_passive_budget(msg_id: str) -> bool:\n'
            '    """Return True when the passive-reply budget for *msg_id* is still available."""\n'
            '    with _passive_reply_lock:\n'
            '        n = _passive_reply_count.get(msg_id, 0)\n'
            '        if n >= _QQ_PASSIVE_REPLY_LIMIT:\n'
            '            return False\n'
            '        _passive_reply_count[msg_id] = n + 1\n'
            '        if len(_passive_reply_count) > 1000:\n'
            '            for k in list(_passive_reply_count.keys())[:500]:\n'
            '                del _passive_reply_count[k]\n'
            '        return True'
        )
        data = _patch(data, old, new)
        changed = True
        print("[patch-hg] passive budget counter applied")
    else:
        print("[patch-hg] passive budget counter already applied")

    # ---- Patch 4: budget check in _send_message + media-first content ----
    if "passive reply budget exhausted" not in data:
        old = (
            '            msg_id = payload.get("msg_id") or meta.get("msg_id")\n'
            '            if msg_id:\n'
            '                # Passive reply: include msg_id and msg_seq\n'
            '                payload.setdefault("msg_id", msg_id)\n'
            '                payload["msg_seq"] = _get_next_msg_seq(msg_id)\n'
            '            else:\n'
            '                # Proactive message: omit msg_id/msg_seq per QQ docs\n'
            '                payload.pop("msg_seq", None)'
        )
        new = (
            '            msg_id = payload.get("msg_id") or meta.get("msg_id")\n'
            '            if msg_id:\n'
            '                # Passive reply budget: QQ allows at most 5 replies per passive\n'
            '                # message. Once exhausted, fall back to a proactive message so\n'
            '                # multi-image replies still reach the group.\n'
            '                if not _consume_passive_budget(msg_id):\n'
            '                    logger.warning(\n'
            '                        "QQChannel passive reply budget exhausted for %s, sending as proactive",\n'
            '                        msg_id,\n'
            '                    )\n'
            '                    payload.pop("msg_id", None)\n'
            '                    payload.pop("msg_seq", None)\n'
            '                else:\n'
            '                    # Passive reply: include msg_id and msg_seq\n'
            '                    payload.setdefault("msg_id", msg_id)\n'
            '                    payload["msg_seq"] = _get_next_msg_seq(msg_id)\n'
            '            else:\n'
            '                # Proactive message: omit msg_id/msg_seq per QQ docs\n'
            '                payload.pop("msg_seq", None)'
        )
        data = _patch(data, old, new)
        changed = True
        print("[patch-hg] budget check applied")
    else:
        print("[patch-hg] budget check already applied")

    if "stopping batch" not in data:
        old = (
            '        # Send text content\n'
            '        if text_parts:\n'
            '            payload: dict[str, Any] = {"content": "\\n".join(text_parts)}\n'
            '            if msg_id:\n'
            '                payload["msg_id"] = msg_id\n'
            '            await self._send_message(subject.subject_id, payload, msg_type, meta)\n'
            '\n'
            '        # Send media items individually\n'
            '        for media in media_parts:\n'
            '            await self._send_media(subject, media)'
        )
        new = (
            '        # Send media items first: the passive reply budget (5 replies per\n'
            '        # passive message) is better spent on images; text goes last.\n'
            '        for media in media_parts:\n'
            '            try:\n'
            '                await self._send_media(subject, media)\n'
            '            except Exception:\n'
            '                # Passive budget exhausted and proactive send unavailable:\n'
            '                # stop the batch instead of failing every remaining item.\n'
            '                logger.exception("QQChannel media send failed, stopping batch")\n'
            '                return\n'
            '\n'
            '        # Send text content last (within the remaining passive budget).\n'
            '        if text_parts:\n'
            '            payload: dict[str, Any] = {"content": "\\n".join(text_parts)}\n'
            '            if msg_id:\n'
            '                payload["msg_id"] = msg_id\n'
            '            try:\n'
            '                await self._send_message(subject.subject_id, payload, msg_type, meta)\n'
            '            except Exception:\n'
            '                logger.exception("QQChannel text send failed")'
        )
        data = _patch(data, old, new)
        changed = True
        print("[patch-hg] media-first content applied")
    else:
        print("[patch-hg] media-first content already applied")

    if changed:
        target.write_text(data, encoding="utf-8")
        print(f"[patch-hg] channel.py patched: {target}")
    else:
        print("[patch-hg] no changes needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
