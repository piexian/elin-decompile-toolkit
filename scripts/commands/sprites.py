"""sprites 子命令：裁剪角色/物品精灵图。"""

import argparse
import sys
from pathlib import Path

from .. import sprites
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    """sprites 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="scripts sprites", description="按图集矩形逻辑裁剪角色/物品精灵"
    )
    parser.add_argument("ids", nargs="+", help="角色 id 或物品 id")
    parser.add_argument("--workspace", required=True, type=Path, help="版本工作区目录")
    parser.add_argument("--game", type=Path, default=None, help="Elin 游戏目录（默认 ELIN_GAME_DIR / Steam）")
    parser.add_argument("--trim", action="store_true", help="物品按 alpha 包围盒紧裁（默认整格）")
    parser.add_argument("--snow", action="store_true", help="角色取冬装图块")
    parser.add_argument("--tile", type=int, default=None, help="直接指定图块线性索引")
    parser.add_argument("--outdir", type=Path, default=None, help="输出目录（默认 workspace/reports/sprites）")
    parser.add_argument("--name", default=None, help="输出文件名（不含扩展名）")
    args = parser.parse_args(argv)
    try:
        sprites.sprites(
            args.workspace, args.ids, args.game,
            args.trim, args.snow, args.tile, args.outdir, args.name,
        )
    except ElinToolError as e:
        print(f"sprites 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
