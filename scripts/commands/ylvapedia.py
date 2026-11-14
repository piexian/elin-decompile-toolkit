"""ylvapedia 子命令：获取页面和修订信息到本地缓存。"""

import argparse
import sys
from pathlib import Path

from .. import ylvapedia
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="scripts ylvapedia", description="读取 Ylvapedia 补充数据")
    sub = parser.add_subparsers(dest="action", required=True)
    for action, help_text in (
        ("fetch", "获取页面 wikitext 和修订信息"),
        ("revisions", "查询页面最新修订"),
    ):
        p = sub.add_parser(action, help=help_text)
        p.add_argument("--workspace", required=True, type=Path)
        p.add_argument("--page", required=True, help="Ylvapedia 完整页面名，如 Elin:Gods")
        p.add_argument("--outdir", type=Path, default=None, help="缓存目录（默认 workspace/ylvapedia/cache）")
    args = parser.parse_args(argv)
    try:
        func = ylvapedia.fetch if args.action == "fetch" else ylvapedia.revisions
        func(args.workspace, args.page, args.outdir)
    except ElinToolError as e:
        print(f"ylvapedia {args.action} 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
