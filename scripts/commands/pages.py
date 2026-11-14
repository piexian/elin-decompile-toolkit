"""pages 子命令：生成 wiki 草稿（角色表/角色页/地点页）。"""

import argparse
import sys
from pathlib import Path

from .. import enrichment, pages
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    """pages 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(prog="scripts pages", description="生成 wiki 草稿")
    sub = parser.add_subparsers(dest="action", required=True)
    p1 = sub.add_parser("chara-table", help="重生成站内 [[角色表]] 数据表")
    p1.add_argument("--workspace", required=True, type=Path)
    p1.add_argument("--output", type=Path, default=None, help="输出文件（默认 workspace/reports/pages/角色表-重生成.md）")
    p2 = sub.add_parser("characters", help="生成独特 NPC 角色页草稿")
    p2.add_argument("--workspace", required=True, type=Path)
    p2.add_argument("--game", type=Path, default=None, help="Elin 游戏目录（默认 ELIN_GAME_DIR / Steam）")
    p2.add_argument("names", nargs="*", help="只生成这些页名/角色 id（缺省全部）")
    p3 = sub.add_parser("zones", help="生成缺失地点页草稿")
    p3.add_argument("--workspace", required=True, type=Path)
    p4 = sub.add_parser("gods", help="从官方 Religion 数据生成神祇/神仆页草稿")
    p4.add_argument("--workspace", required=True, type=Path)
    p4.add_argument("--output", type=Path, default=None)
    p5 = sub.add_parser("enrich-ylvapedia", help="生成 Ylvapedia 角色补充审阅稿")
    p5.add_argument("--workspace", required=True, type=Path)
    p5.add_argument("--output", type=Path, default=None)
    p5.add_argument("ids", nargs="+", help="官方 Chara ID，如 loytel")
    args = parser.parse_args(argv)
    try:
        if args.action == "chara-table":
            pages.chara_table(args.workspace, args.output)
        elif args.action == "characters":
            pages.characters(args.workspace, args.game, args.names)
        elif args.action == "zones":
            pages.zones(args.workspace)
        elif args.action == "gods":
            enrichment.gods(args.workspace, args.output)
        else:
            enrichment.enrich_characters(args.workspace, args.ids, args.output)
    except ElinToolError as e:
        print(f"pages {args.action} 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
