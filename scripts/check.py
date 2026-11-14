"""check 子命令：校验游戏目录完整性。"""
import argparse
import sys
from pathlib import Path

from .errors import GameIncompleteError, PathNotFoundError

REQUIRED_FILES = [
    "Elin_Data/Managed/Elin.dll",
    "Elin_Data/sharedassets0.assets",
]
CN_LANG_DIR = "Package/_Lang_Chinese/Lang/CN"


def check_game(game_dir: Path) -> None:
    """检查 Elin.dll、sharedassets0.assets 与简中语言目录，缺失即抛错。"""
    game_dir = game_dir.resolve()
    if not game_dir.is_dir():
        raise PathNotFoundError(f"游戏目录不存在：{game_dir}")

    missing = [rel for rel in REQUIRED_FILES if not (game_dir / rel).is_file()]
    if not (game_dir / CN_LANG_DIR).is_dir():
        missing.append(CN_LANG_DIR)
    if missing:
        raise GameIncompleteError(f"游戏目录不完整，缺少：{'、'.join(missing)}")

    print(f"check 通过：{game_dir}")
    for rel in REQUIRED_FILES:
        print(f"  ok {rel}")
    print(f"  ok {CN_LANG_DIR}")


def main(argv: list[str]) -> int:
    """check 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(prog="scripts check", description="校验游戏目录完整性")
    parser.add_argument("--game", required=True, type=Path, help="Elin 游戏目录")
    args = parser.parse_args(argv)
    try:
        check_game(args.game)
    except (PathNotFoundError, GameIncompleteError) as e:
        print(f"check 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
