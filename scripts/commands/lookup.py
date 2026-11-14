"""lookup 子命令：按 id/官方名/中文名检索工作区数据。"""

import argparse
import sys
from pathlib import Path

from .. import lookup
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    """lookup 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="scripts lookup",
        description="按 id/中文名/英文名/日文名 模糊检索（表：all/thing/mat/cat/ele）",
    )
    parser.add_argument("--workspace", required=True, type=Path, help="版本工作区目录")
    parser.add_argument(
        "words", nargs="+",
        help="[all|thing|mat|cat|ele] 关键词（表名可省略，默认 all）",
    )
    args = parser.parse_args(argv)
    words = args.words
    if words[0] in lookup.TABLES and len(words) > 1:
        table, query = words[0], " ".join(words[1:])
    elif words[0] in lookup.TABLES:
        parser.error("缺少查询关键词")
    else:
        table, query = "all", " ".join(words)
    try:
        lookup.lookup(args.workspace, table, query)
    except ElinToolError as e:
        print(f"lookup 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
