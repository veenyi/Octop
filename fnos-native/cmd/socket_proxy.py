#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Octop 本地版 — Unix Socket -> TCP 代理
飞牛统一网关通过 app.sock 访问应用，但 Octop 后端只监听 TCP 端口。
本代理绑定 $APPDEST/app.sock，把网关转发来的 HTTP 请求透传给 Octop 的 TCP 端口。
"""
import os
import select
import socket
import sys
import threading


APP_SOCK = sys.argv[1] if len(sys.argv) > 1 else "/var/apps/octop-native/app.sock"
BACKEND_HOST = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
BACKEND_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8088
BACKEND = (BACKEND_HOST, BACKEND_PORT)


def relay(a: socket.socket, b: socket.socket) -> None:
    """双向转发数据直到一方关闭。"""
    try:
        while True:
            readable, _, _ = select.select([a, b], [], [], 1.0)
            for src in readable:
                dst = b if src is a else a
                data = src.recv(65536)
                if not data:
                    return
                dst.sendall(data)
    except OSError:
        pass


def handle_client(client: socket.socket) -> None:
    """处理一次 socket 连接。"""
    backend = None
    try:
        backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend.connect(BACKEND)
        relay(client, backend)
    except Exception as exc:
        print(f"[socket_proxy] backend connect failed: {exc}", file=sys.stderr)
    finally:
        client.close()
        if backend is not None:
            backend.close()


def main() -> None:
    # 清理旧 socket
    if os.path.exists(APP_SOCK):
        try:
            os.unlink(APP_SOCK)
        except OSError as exc:
            print(f"[socket_proxy] warning: cannot remove old socket: {exc}", file=sys.stderr)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.bind(APP_SOCK)
        s.listen(128)
        print(f"[socket_proxy] listening on {APP_SOCK} -> {BACKEND}")
        while True:
            client, _ = s.accept()
            t = threading.Thread(target=handle_client, args=(client,), daemon=True)
            t.start()
    finally:
        s.close()
        if os.path.exists(APP_SOCK):
            try:
                os.unlink(APP_SOCK)
            except OSError:
                pass


if __name__ == "__main__":
    main()
