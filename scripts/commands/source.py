"""source 子命令：按类拆分反编译源码。"""

import argparse
import sys
from pathlib import Path

from .. import source
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    """source 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="scripts source", description="按类拆分反编译源码"
    )
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("split", help="拆分源码到 kb/source/classes")
    p.add_argument("--workspace", required=True, type=Path, help="版本工作区目录")
    p.add_argument(
        "--input", type=Path, default=None,
        help="输入：反编译单文件或项目目录（默认 workspace/src/Elin.decompiled.cs）",
    )
    p.add_argument(
        "--output", type=Path, default=None,
        help="输出目录（默认 workspace/kb/source/classes）",
    )
    args = parser.parse_args(argv)
    try:
        source.split(args.workspace, args.input, args.output)
    except ElinToolError as e:
        print(f"source split 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
