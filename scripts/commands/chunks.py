"""chunks 子命令：打包 AstrBot 上传聚合文件。"""

import argparse
import sys
from pathlib import Path

from .. import chunks
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    """chunks 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="scripts chunks", description="打包 kb/corpus 为 AstrBot 上传聚合文件"
    )
    parser.add_argument("--workspace", required=True, type=Path, help="版本工作区目录")
    parser.add_argument("--size", type=int, default=chunks.DEFAULT_SIZE, help=f"WebUI 分块大小（默认 {chunks.DEFAULT_SIZE}）")
    parser.add_argument("--code", action="store_true", help="包含反编译代码语料（默认停传）")
    args = parser.parse_args(argv)
    try:
        chunks.build(args.workspace, args.size, skip_code=not args.code)
    except ElinToolError as e:
        print(f"chunks 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
