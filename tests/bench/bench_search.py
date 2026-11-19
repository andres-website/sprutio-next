"""Замер поиска по имени и по содержимому через API sprutio.

  venv/bin/python tests/bench/bench_search.py sftp ./project [fast]
  venv/bin/python tests/bench/bench_search.py home /home/fmtest/project [fast]
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from conftest import _env  # noqa: E402
from fmclient import FMClient  # noqa: E402
from test_remote import RemoteClient, create_conn, remove_conn  # noqa: E402

kind, path = sys.argv[1], sys.argv[2]
fast = len(sys.argv) > 3 and sys.argv[3] == "fast"
e = _env()
c = FMClient()
c.login(e["FM_TEST_USER"], e["FM_TEST_PASS"])
c.init_session()
conn = None
if kind == "home":
    client = c
else:
    conn = create_conn(c, kind)
    client = RemoteClient(c, kind, int(conn["id"]))
    client.init_session()


def run(url, params):
    if fast:
        params = dict(params, fast=True)
    t = time.time()
    st = client.op(url, {"params": params, "session": client.session(path)}, timeout=3600)
    return time.time() - t, st


try:
    dt, st = run("/actions/find/files", {"path": path, "filename": "needle*", "file_size": 0, "type_dir": True,
                                          "type_file": True, "size_direction": "more"})
    print("%-6s %-5s by name   : %7.2fs  found=%s" % (kind, "fast" if fast else "orig", dt,
                                                        sorted(i["name"] for i in st["data"])))
    dt, st = run("/actions/find/text", {"path": path, "text": "UNIQUE_NEEDLE_7731"})
    print("%-6s %-5s by content: %7.2fs  found=%s" % (kind, "fast" if fast else "orig", dt,
                                                        sorted(i["name"] for i in st["data"])))
finally:
    if conn:
        remove_conn(c, kind, conn["id"])
