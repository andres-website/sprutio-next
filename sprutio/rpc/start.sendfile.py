#!/usr/bin/env python
"""
Приём загружаемых файлов от app (UploadHandler) и запись их во временный каталог rpc.

Форк: asyncore/asynchat удалены в Python 3.12 — сервер переписан на socketserver.
Протокол прежний:
    36 байт  — размер потока (заголовок + тело), big-endian
     2 байта — длина пути, big-endian
     N байт  — путь временного файла (utf-8)
     ...     — тело файла
Новое: по окончании записи сервер отвечает b"OK\\n" (или b"ERR ...\\n"), чтобы клиент не запускал
обработку загрузки до того, как файл записан целиком.
"""
import os
import socket
import socketserver
import sys
import traceback

from misc import helpers
from misc import logger

RPC_SENDFILE_HOST = os.getenv('FM_RPC_SENDFILE_HOST', 'localhost')
RPC_SENDFILE_PORT = int(os.getenv('FM_RPC_SENDFILE_PORT', 51600))
RPC_SENDFILE_PROGRAM_NAME = os.getenv("FM_RPC_SENDFILE_PROGRAM_NAME", 'fm-rpc-sendfile')
RPC_SENDFILE_DEFAULT_LOGFILE = os.getenv("FM_RPC_SENDFILE_LOGFILE", '../logs/%s.log' % RPC_SENDFILE_PROGRAM_NAME)
RPC_SENDFILE_TIMEOUT = int(os.getenv('FM_RPC_SENDFILE_TIMEOUT', 600))
SOCKET_SIZE_LENGTH = 36
SOCKET_HEADER_LENGTH = 2
CHUNK = 1024 * 1024


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(CHUNK, n - len(buf)))
        if not chunk:
            raise EOFError("connection closed: got %d of %d bytes" % (len(buf), n))
        buf += chunk
    return bytes(buf)


class FileStreamHandler(socketserver.BaseRequestHandler):
    def handle(self):
        log = logger.get_logger()
        sock = self.request
        sock.settimeout(RPC_SENDFILE_TIMEOUT)
        path = None
        try:
            size = int.from_bytes(recv_exact(sock, SOCKET_SIZE_LENGTH), byteorder='big')
            header_len = int.from_bytes(recv_exact(sock, SOCKET_HEADER_LENGTH), byteorder='big')
            path = recv_exact(sock, header_len).decode('utf-8')
            body_len = size - SOCKET_HEADER_LENGTH - header_len
            if body_len < 0:
                raise ValueError("bad stream size %d for header %d" % (size, header_len))

            log.info("sendfile: receiving %s (%d bytes)", path, body_len)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            left = body_len
            with open(path, 'wb') as fd:
                while left > 0:
                    chunk = sock.recv(min(CHUNK, left))
                    if not chunk:
                        raise EOFError("connection closed: %d bytes left" % left)
                    fd.write(chunk)
                    left -= len(chunk)
            sock.sendall(b"OK\n")
            log.info("sendfile: done %s", path)
        except Exception as e:
            log.error("sendfile: error for %s: %s\n%s", path, e, traceback.format_exc())
            try:
                sock.sendall(("ERR %s\n" % e).encode('utf-8', 'replace'))
            except OSError:
                pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, 'SO_REUSEPORT'):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        super().server_bind()


if __name__ == "__main__":
    print("FM back-end RPC server")
    print("--------------------------")
    print("HOSTNAME: %s" % helpers.get_hostname())

    try:
        logger.setup_logger(RPC_SENDFILE_DEFAULT_LOGFILE)
        print("LOGFILE: %s" % os.path.realpath(RPC_SENDFILE_DEFAULT_LOGFILE))
        server = Server((RPC_SENDFILE_HOST, RPC_SENDFILE_PORT), FileStreamHandler)
        logger.get_logger().info("LISTEN %s:%s" % server.server_address)
        sys.stdout.write("\nstarting transfer:\n")
        sys.stdout.flush()
        server.serve_forever()
    except Exception as e:
        print("Got an exception: %s" % str(e))
        print(traceback.format_exc())
        sys.exit(1)
