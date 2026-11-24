"""Симлинки: rpc форка сообщает, куда ведёт ссылка (link_type / link_target / link_resolved).

Домашний сервер — ссылки создаются прямо в песочнице стенда (stand/sandbox-root = /mnt в rpc).
Абсолютная цель разрешается от корня песочницы, а не от корня контейнера rpc.
"""
import os
import subprocess

import pytest

from test_remote import RemoteClient, create_conn, remove_conn, conn_params  # noqa: F401

pytestmark = pytest.mark.fork_only("сведения о цели симлинка")

SANDBOX = os.path.join(os.path.dirname(__file__), "..", "..", "stand", "sandbox-root")


def host(path):
    return os.path.join(SANDBOX, path.lstrip("/"))


def test_home_links(fm, work):
    fm.mkdir(work + "/dir")
    fm.newfile(work + "/dir/file.txt")
    fm.write(work + "/dir/file.txt", "hello")
    links = {"abs_dir": work + "/dir", "rel_file": "dir/file.txt", "broken": "/nowhere/at/all",
             "escape": "../../../../../../etc"}
    for name, target in links.items():
        os.symlink(target, host(work + "/" + name))
    items = fm.ls(work)
    assert items["abs_dir"]["is_link"] and items["abs_dir"]["link_type"] == "dir"
    assert items["abs_dir"]["link_target"] == work + "/dir"
    assert items["abs_dir"]["link_resolved"] == work + "/dir"
    assert items["rel_file"]["link_type"] == "file"
    assert items["rel_file"]["link_resolved"] == work + "/dir/file.txt"
    assert items["broken"]["link_type"] == "broken"
    assert items["escape"]["link_type"] == "broken"
    # открыть цель по link_resolved — то, что делает фронт
    assert "file.txt" in fm.ls(items["abs_dir"]["link_resolved"])
    # удаление папки со ссылкой не трогает цель ссылки вне неё
    os.makedirs(host(work + "-target"), exist_ok=True)
    try:
        open(host(work + "-target/keep.txt"), "w").write("x")
        os.symlink(work + "-target", host(work + "/dir/outside"))
        fm.remove([work + "/dir"])
        assert os.path.exists(host(work + "-target/keep.txt"))
    finally:
        subprocess.run(["rm", "-rf", host(work + "-target")])


def test_sftp_links(fm):
    d = create_conn(fm, "sftp")
    remote = RemoteClient(fm, "sftp", int(d["id"]))
    remote.init_session()
    sh = lambda c: subprocess.run(["docker", "exec", "sprutio-sshd-1", "sh", "-c", c],
                                  capture_output=True, text=True, timeout=60)
    home = sh("getent passwd %s | cut -d: -f6" % conn_params("sftp")["user"]).stdout.strip()
    base = home + "/t-links"
    try:
        r = sh("rm -rf {b} && mkdir -p {b}/dir && echo hi > {b}/dir/f.txt && ln -s {b}/dir {b}/to_dir && "
               "ln -s dir/f.txt {b}/to_file && ln -s /nowhere {b}/broken && chown -R $(stat -c %u {h}) {b}"
               .format(b=base, h=home))
        assert r.returncode == 0, r.stderr
        items = remote.ls(base)
        assert items["to_dir"]["is_link"] and items["to_dir"]["link_type"] == "dir"
        assert items["to_dir"]["link_target"] == base + "/dir"
        assert items["to_file"]["link_type"] == "file"
        assert items["broken"]["link_type"] == "broken"
        assert "f.txt" in remote.ls(base + "/to_dir")
    finally:
        sh("rm -rf " + base)
        remove_conn(fm, "sftp", d["id"])
