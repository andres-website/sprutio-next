# -*- coding: utf-8 -*-
"""
Минимальный синхронный клиент протокола MessagePack-RPC.

Заменяет пакет msgpack-rpc-python (msgpackrpc), который построен на tornado<5 и не работает
на современных Python/Tornado. Формат на проводе совместим с оригиналом:
  запрос  [0, msgid, method, params]
  ответ   [1, msgid, error, result]
Строки упаковываются как raw (use_bin_type=False) и распаковываются в bytes (raw=True) —
ровно как это делал msgpack 0.4, на поведение которого рассчитаны beget_msgpack и rpc.
"""
import itertools
import socket

import msgpack


class RpcError(Exception):
    pass


class TimeoutError(RpcError):
    pass


class TransportError(RpcError):
    pass


_msgid = itertools.count(1)


def pack(obj):
    return msgpack.packb(obj, use_bin_type=False)


def unpacker():
    return msgpack.Unpacker(raw=True, strict_map_key=False, max_buffer_size=512 * 1024 * 1024)


class Client(object):
    def __init__(self, host, port, timeout=30):
        self.host = host
        self.port = int(port)
        self.timeout = timeout

    def call(self, method, *params):
        msgid = next(_msgid) & 0xFFFFFFFF
        payload = pack([0, msgid, method, list(params)])
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except socket.timeout as e:
            raise TimeoutError(str(e))
        except OSError as e:
            raise TransportError(str(e))

        try:
            sock.sendall(payload)
            up = unpacker()
            while True:
                try:
                    chunk = sock.recv(65536)
                except socket.timeout as e:
                    raise TimeoutError(str(e))
                if not chunk:
                    raise TransportError("connection closed before response")
                up.feed(chunk)
                for message in up:
                    if not isinstance(message, (list, tuple)) or len(message) != 4 or message[0] != 1:
                        raise TransportError("bad response: %r" % (message,))
                    error, result = message[2], message[3]
                    if error is not None:
                        raise RpcError(error)
                    return result
        finally:
            sock.close()
