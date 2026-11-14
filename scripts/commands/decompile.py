"""decompile 子命令：ilspycmd 反编译 Elin.dll 到工作区 src。"""

import argparse
import sys
from pathlib import Path

from .. import decompile
from ..errors import ElinToolError


def main(argv: list[str]) -> int:
    """decompile 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="scripts decompile", description="反编译游戏主 DLL 到工作区 src"
    )
    parser.add_argument("--workspace", required=True, type=Path, help="版本工作区目录")
    parser.add_argument(
        "--game", type=Path, default=None,
        help="Elin 游戏目录（默认取工作区登记、ELIN_GAME_DIR 或 Steam 发现）",
    )
    parser.add_argument("--project", action="store_true", help="ilspycmd -p 生成工程文件")
    args = parser.parse_args(argv)
    try:
        decompile.decompile(args.workspace, args.game, args.project)
    except ElinToolError as e:
        print(f"decompile 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
