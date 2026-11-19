import json
import os
import random
import socket
import time

from tornado import web

from config.server import SENDFILE_DEFAULT_HOST, SENDFILE_DEFAULT_PORT
from core import FM
from handlers.BaseHandler import BaseHandler, wrap_async_rpc, wrap_catch

SENDFILE_BUFFER_SIZE = 4096


class UploadHandler(BaseHandler):
    @staticmethod
    def random_hash():
        hash_str = random.getrandbits(128)
        return "%032x" % hash_str

    @wrap_async_rpc
    @wrap_catch
    @web.authenticated
    def post(self):

        fname = self.request.headers.get("X-File-Name").encode('utf-8')
        fname = fname.decode('unicode_escape')
        overwrite = self.get_argument("overwrite")
        session = json.loads(self.get_argument("session"))

        if overwrite == 'false':
            overwrite = False
        else:
            overwrite = True

        temp_dir = '/tmp/fm/' + str(self.get_current_user()) + '/upload/' + str(round(time.time())) + '/'
        tmp_file = os.path.join(temp_dir, fname)

        # here IDE alert is wrong (byte/str)
        nginx_file = os.path.join('/tmp/nginx/' + self.random_hash() + '/', fname)
        if not os.path.exists(os.path.dirname(nginx_file)):
            os.makedirs(os.path.dirname(nginx_file))

        # кодируем имя временного файла в заголовке потока
        header = (len(tmp_file.encode("utf-8"))).to_bytes(2, byteorder='big') + tmp_file.encode("utf-8")

        fp = open(nginx_file, "wb")
        fp.write(header)
        fp.write(self.request.body)
        fp.close()

        size = os.path.getsize(nginx_file).to_bytes(36, byteorder='big')

        file = open(nginx_file, "rb")
        sock = socket.socket()
        sock.connect((SENDFILE_DEFAULT_HOST, SENDFILE_DEFAULT_PORT))

        # отправляем размер файла, затем поток целиком (sendall: send() мог отправить не всё)
        try:
            sock.sendall(size)
            while True:
                data = file.read(SENDFILE_BUFFER_SIZE)
                if not data:
                    break  # EOF
                sock.sendall(data)

            # форк: ждём подтверждения записи от rpc, иначе обработка загрузки может начаться
            # раньше, чем файл записан целиком
            sock.settimeout(600)
            reply = b''
            while not reply.endswith(b"\n"):
                chunk = sock.recv(1024)
                if not chunk:
                    break
                reply += chunk
            if not reply.startswith(b"OK"):
                raise Exception("sendfile failed: %r" % reply)
        finally:
            sock.close()
            file.close()

        os.remove(nginx_file)
        action = self.get_action(name=FM.Actions.UPLOAD, module=session.get('type'), session=session,
                                 file_path=tmp_file, overwrite=overwrite)
        answer = action.run()

        self.json(answer)
        self.finish()
