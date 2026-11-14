"""diff 子命令：对比两个版本工作区的源码与语言包。"""

import argparse
import sys
from pathlib import Path

from .. import diff
from ..errors import ElinToolError, WorkspaceError


def main(argv: list[str]) -> int:
    """diff 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="scripts diff", description="对比两个版本工作区"
    )
    sub = parser.add_subparsers(dest="action", required=True)
    for name, desc in (
        ("code", "按类型归属对比 src 源码"),
        ("lang", "按表与实体 ID 对比 data/lang"),
    ):
        p = sub.add_parser(name, help=desc)
        p.add_argument("--old", required=True, type=Path, help="旧版本工作区")
        p.add_argument("--new", required=True, type=Path, help="新版本工作区")
        p.add_argument("--output", type=Path, default=None, help="报告写入文件（默认 stdout）")
    args = parser.parse_args(argv)
    try:
        if args.action == "code":
            report = diff.diff_code(args.old, args.new)
        else:
            report = diff.diff_lang(args.old, args.new)
        if args.output:
            try:
                args.output.write_text(report, encoding="utf-8")
            except OSError as e:
                raise WorkspaceError(f"写出报告失败 {args.output}：{e}") from e
            print(f"报告已写入：{args.output}")
        else:
            print(report, end="")
    except ElinToolError as e:
        print(f"diff {args.action} 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
