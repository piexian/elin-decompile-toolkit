"""corpus 子命令：构建 RAG 语料。"""

import argparse
import sys
from pathlib import Path

from .. import corpus
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    """corpus 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(prog="scripts corpus", description="构建 RAG 语料")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("build", help="渲染 workspace/kb/corpus")
    p.add_argument("--workspace", required=True, type=Path, help="版本工作区目录")
    args = parser.parse_args(argv)
    try:
        corpus.build(args.workspace)
    except ElinToolError as e:
        print(f"corpus build 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
