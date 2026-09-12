# -*- coding: utf-8 -*-
"""生成 SHA256 校验和文件: <asset>.sha256, 内容为 "<hex>  <文件名>"。

用法: python scripts/make_checksum.py <文件路径> [<文件路径> ...]

配套 updater.resolve_expected_sha256 / parse_checksum_for —— 发布时每个安装包
都带上 .sha256 资产, 客户端下载后先校验再替换, 挡住中间人和半截下载。
"""
import hashlib
import os
import sys


def _force_utf8_stdio():
    """Windows runner 的 stdout 默认 cp1252，打印中文文件名会 UnicodeEncodeError。

    GitHub Actions windows-latest 上 Python 输出走管道时按 ANSI 代码页(cp1252)编码，
    含中文的路径(如 校园网连接管家-v5.2.1-win64.exe)会崩。强制 UTF-8 规避。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def sha256_of_file(path, chunk_size=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def main(paths):
    if not paths:
        print(__doc__)
        return 2
    rc = 0
    for path in paths:
        if not os.path.isfile(path):
            print("跳过（文件不存在）: %s" % path)
            rc = 1
            continue
        digest = sha256_of_file(path)
        out_path = path + ".sha256"
        # 文件名可能含中文(如 校园网连接管家-v5.2.1-win64.exe), 必须用 UTF-8 写,
        # 否则 ascii 编码在 Windows 上会 UnicodeEncodeError。客户端 parse_checksum_for
        # 用 utf-8(errors=replace) 读取 + lower/endswith 匹配, 双向一致。
        with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("%s  %s\n" % (digest, os.path.basename(path)))
        print("%s  ->  %s" % (digest, out_path))
    return rc


if __name__ == "__main__":
    _force_utf8_stdio()
    sys.exit(main(sys.argv[1:]))
