import logging
import os

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

logging.basicConfig(level=logging.WARNING)

authorizer = DummyAuthorizer()
authorizer.add_user(os.environ["FTP_USER"], os.environ["FTP_PASS"], "/data", perm="elradfmwMT")

handler = FTPHandler
handler.authorizer = authorizer
handler.passive_ports = range(30000, 30010)
handler.encoding = "utf-8"

FTPServer(("0.0.0.0", 21), handler).serve_forever()
