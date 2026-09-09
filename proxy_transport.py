"""Bounded TCP relay. No payload logging or TLS inspection."""
import select
import socket
import time


def relay(a, b, first=b"", *, idle_timeout=300, on_bytes=None,
          on_error=None, should_stop=lambda: False):
    sockets = (a, b)
    # pending[i] is data waiting to be sent TO socket i.
    pending = [bytearray(), bytearray(first)]
    eof = [False, False]
    shut = [False, False]
    last_activity = time.monotonic()
    for sock in sockets:
        sock.setblocking(False)
    try:
        while not should_stop():
            for i in (0, 1):
                if eof[1-i] and not pending[i] and not shut[i]:
                    try:
                        sockets[i].shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    shut[i] = True
            if all(eof) and not any(pending):
                return
            remaining = idle_timeout - (time.monotonic() - last_activity)
            if remaining <= 0:
                raise TimeoutError("relay idle")
            reads = [sockets[i] for i in (0, 1)
                     if not eof[i] and len(pending[1-i]) < 262144]
            writes = [sockets[i] for i in (0, 1) if pending[i]]
            readable, writable, _ = select.select(reads, writes, [], min(remaining, 0.5))
            for sock in readable:
                i = sockets.index(sock)
                try:
                    chunk = sock.recv(65536)
                except BlockingIOError:
                    continue
                if chunk:
                    pending[1-i].extend(chunk)
                    last_activity = time.monotonic()
                else:
                    eof[i] = True
            for sock in writable:
                i = sockets.index(sock)
                try:
                    sent = sock.send(pending[i])
                except BlockingIOError:
                    continue
                if not sent:
                    raise ConnectionError("zero write")
                del pending[i][:sent]
                last_activity = time.monotonic()
                if on_bytes:
                    on_bytes("upload" if i == 1 else "download", sent)
    except (OSError, ValueError) as exc:
        if not should_stop() and on_error:
            on_error("传输空闲超时" if isinstance(exc, TimeoutError) else
                     "传输连接中断 (%s)" % type(exc).__name__)
    finally:
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def forward_head(lines, method, target):
    """Preserve negotiated Upgrade; normal HTTP remains single-request."""
    headers = [line.split(b":", 1) for line in lines[1:] if b":" in line]
    connections = {token.strip().lower() for key, value in headers
                   if key.lower() == b"connection" for token in value.split(b",")}
    upgrade = b"upgrade" in connections and any(
        key.lower() == b"upgrade" and value.strip() for key, value in headers)
    excluded = {b"connection", b"proxy-connection", b"proxy-authorization", b"x-shared-key"}
    out = [method + b" " + target + b" HTTP/1.1"]
    out.extend(line for line in lines[1:] if line.split(b":", 1)[0].lower() not in excluded)
    out.append(b"Connection: Upgrade" if upgrade else b"Connection: close")
    return b"\r\n".join(out) + b"\r\n\r\n"
