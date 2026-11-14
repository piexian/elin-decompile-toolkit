"""workspace 子命令：创建并登记版本工作区。"""

import argparse
import hashlib
import json
import shutil
import sys
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from .check import REQUIRED_FILES, check_game
from .errors import ElinToolError, WorkspaceError

WORKSPACE_DIRS = ["data", "src", "kb", "reports"]
VERSION_JSON = "version.json"
CHANNELS = ("stable", "nightly")


def _sha256(path: Path) -> str:
    """计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_component(name: str, value: str) -> None:
    """拒绝空值、.、.. 和含路径分隔符的组件，防止越出工作区根目录。"""
    if not value or value in (".", "..") or "/" in value or "\\" in value:
        raise WorkspaceError(f"非法的 {name}：{value!r}")


def _discard_failed(workspace: Path, channel_root: Path) -> None:
    """删除创建失败的工作区目录与空 channel 目录。"""
    shutil.rmtree(workspace, ignore_errors=True)
    with suppress(OSError):
        channel_root.rmdir()


def workspace_init(channel: str, version: str, game_dir: Path, root: Path) -> Path:
    """创建工作区目录并写入 version.json，返回工作区路径。"""
    _validate_component("channel", channel)
    _validate_component("version", version)
    check_game(game_dir)

    root = root.resolve()
    if root.exists() and not root.is_dir():
        raise WorkspaceError(f"root 不是目录：{root}")
    channel_root = root / channel
    if channel_root.is_symlink():
        raise WorkspaceError(f"channel 目录是符号链接：{channel_root}")
    workspace = channel_root / version
    if workspace.is_symlink():
        raise WorkspaceError(f"工作区是符号链接：{workspace}")
    if workspace.exists():
        raise WorkspaceError(f"工作区已存在：{workspace}")
    try:
        for name in WORKSPACE_DIRS:
            (workspace / name).mkdir(parents=True)

        files = {rel: _sha256(game_dir / rel) for rel in REQUIRED_FILES}
        info = {
            "channel": channel,
            "version": version,
            "game_dir": str(game_dir.resolve()),
            "workspace": str(workspace.resolve()),
            "files": files,
            "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (workspace / VERSION_JSON).write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as e:
        _discard_failed(workspace, channel_root)
        raise WorkspaceError(f"创建工作区失败：{e}") from e

    if not workspace.resolve().is_relative_to(root):
        _discard_failed(workspace, channel_root)
        raise WorkspaceError(f"工作区越出 root：{workspace.resolve()}")
    print(f"工作区已创建：{workspace}")
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return workspace


def main(argv: list[str]) -> int:
    """workspace 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(prog="scripts workspace", description="管理版本工作区")
    sub = parser.add_subparsers(dest="action", required=True)
    p_init = sub.add_parser("init", help="创建版本工作区")
    p_init.add_argument("--channel", required=True, choices=CHANNELS, help="版本通道")
    p_init.add_argument("--version", required=True, help="游戏版本号，如 EA23.182")
    p_init.add_argument("--game", required=True, type=Path, help="Elin 游戏目录")
    p_init.add_argument("--root", required=True, type=Path, help="工作区根目录")
    args = parser.parse_args(argv)
    try:
        workspace_init(args.channel, args.version, args.game, args.root)
    except ElinToolError as e:
        print(f"workspace init 失败：{e}", file=sys.stderr)
        return e.exit_code
    return 0
