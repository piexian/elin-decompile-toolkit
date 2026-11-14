"""decompile 核心：ilspycmd 调用、输出转码为 UTF-8、version.json 更新。"""

import json
import os
import shutil
import subprocess
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from .errors import ElinToolError, ExitCode, PathNotFoundError, WorkspaceError
from .game_assets import find_game_dir
from .workspace import CHANNELS, _sha256

ILSPY_URLS = (
    "ilspycmd 官方地址：https://github.com/icsharpcode/ILSpy"
    "（NuGet：https://www.nuget.org/packages/ilspycmd，"
    "安装：dotnet tool install --global ilspycmd）"
)
MANAGED_DLL_REL = "Elin_Data/Managed/Elin.dll"
ILSPY_TIMEOUT = 1800


class DecompileError(ElinToolError):
    """ilspycmd 执行失败。"""

    exit_code = ExitCode.GAME_INCOMPLETE


def _validate_info(info, vj: Path) -> None:
    """校验 version.json：顶层 dict、channel 合法、version 非空。"""
    if not isinstance(info, dict):
        raise WorkspaceError(f"version.json 顶层必须是 JSON 对象：{vj}")
    if info.get("channel") not in CHANNELS:
        raise WorkspaceError(
            f"version.json 的 channel 必须是 {' 或 '.join(CHANNELS)}：{vj}"
            f"（得到 {info.get('channel')!r}）"
        )
    version = info.get("version")
    if not isinstance(version, str) or not version:
        raise WorkspaceError(f"version.json 的 version 必须是非空字符串：{vj}")


def _load_workspace(ws: Path) -> dict:
    """读取并校验 version.json，失败转 WorkspaceError。"""
    vj = ws / "version.json"
    if not ws.is_dir() or not vj.is_file():
        raise WorkspaceError(f"不是有效工作区（缺 version.json）：{ws}")
    try:
        info = json.loads(vj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise WorkspaceError(f"version.json JSON 损坏 {vj}：{e}") from e
    except OSError as e:
        raise WorkspaceError(f"读取 version.json 失败 {vj}：{e}") from e
    _validate_info(info, vj)
    return info


def _resolve_game_dir(info: dict, explicit: Path | None) -> Path:
    """游戏目录：--game > 工作区登记 > ELIN_GAME_DIR / Steam 发现。"""
    if explicit:
        return find_game_dir(explicit)
    gd = info.get("game_dir")
    if gd:
        game_dir = Path(gd)
        if not game_dir.is_dir():
            raise WorkspaceError(
                f"工作区登记的游戏目录不存在：{game_dir}（可用 --game 覆盖）"
            )
        return game_dir
    return find_game_dir(None)


def _convert_to_utf8(data: bytes) -> str:
    """ilspycmd 输出可能是 GBK：先按 utf-8-sig 严格解，失败再按 cp936 严格解。"""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp936")
    except UnicodeDecodeError as e:
        raise DecompileError(
            f"反编译输出既不是 UTF-8 也不是 GBK，无法解码：{e}。{ILSPY_URLS}"
        ) from e


def decompile(workspace: Path, game: Path | None, project: bool) -> dict:
    """反编译 Elin.dll 到 workspace/src（事务式），临时目录在工作区内并清理。"""
    info = _load_workspace(workspace)
    staging = workspace / ".tmp-decompile"
    backup = staging / "backup"
    if os.path.lexists(backup):
        raise WorkspaceError(
            f"存在上次失败的备份 {backup}，先检查并手动处理后再重试 decompile"
        )
    game_dir = _resolve_game_dir(info, game)
    dll = game_dir / MANAGED_DLL_REL
    if not dll.is_file():
        raise PathNotFoundError(f"找不到游戏主 DLL：{dll}")
    if shutil.which("ilspycmd") is None:
        raise PathNotFoundError(f"找不到 ilspycmd（不自动安装）。{ILSPY_URLS}")

    src = workspace / "src"
    try:
        dll_sha256 = _sha256(dll)
    except OSError as e:
        raise PathNotFoundError(f"读取游戏主 DLL 失败 {dll}：{e}") from e
    try:
        if staging.is_dir():
            shutil.rmtree(staging)
        elif staging.exists():
            staging.unlink()
        raw = staging / "raw"
        norm = staging / "normalized"
        raw.mkdir(parents=True)
        norm.mkdir()
    except OSError as e:
        raise WorkspaceError(f"准备 staging 目录失败 {staging}：{e}") from e

    cmd = ["ilspycmd", "-r", str(dll.parent), "-o", str(raw)]
    if project:
        cmd.append("-p")
    cmd.append(str(dll))
    print(f"游戏: {game_dir}")
    print(f"运行: {' '.join(cmd)}")
    try:
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=ILSPY_TIMEOUT)
        except subprocess.TimeoutExpired as e:
            raise DecompileError(f"ilspycmd 超时（{ILSPY_TIMEOUT}s）。{ILSPY_URLS}") from e
        except OSError as e:
            raise DecompileError(f"ilspycmd 启动失败：{e}。{ILSPY_URLS}") from e
        if proc.returncode != 0:
            tail = proc.stderr.decode("utf-8", "replace").strip()[-500:]
            raise DecompileError(
                f"ilspycmd 失败（exit {proc.returncode}）：{tail or '无 stderr'}。{ILSPY_URLS}"
            )
        count = 0
        for f in sorted(raw.rglob("*")):
            if not f.is_file():
                continue
            dest = norm / f.relative_to(raw)
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(_convert_to_utf8(f.read_bytes()), encoding="utf-8")
            except DecompileError:
                raise
            except OSError as e:
                raise DecompileError(f"归一化写出失败 {dest}：{e}。{ILSPY_URLS}") from e
            count += 1
        if count == 0:
            raise DecompileError(f"ilspycmd 没有产出任何文件。{ILSPY_URLS}")

        # 事务提交：旧 src 改名 backup，staging 归一化产物改名 src；失败即恢复
        src_existed = src.exists() or src.is_symlink()
        if src_existed:
            try:
                os.replace(src, backup)
            except OSError as e:
                raise WorkspaceError(f"备份旧 src 失败：{e}") from e
        try:
            os.replace(norm, src)
        except OSError as e:
            if src_existed:
                try:
                    os.replace(backup, src)
                except OSError as restore_err:
                    raise WorkspaceError(
                        f"替换 src 失败：{e}；恢复旧 src 也失败：{restore_err}"
                        f"（旧输出保留在 {backup}）"
                    ) from e
            raise WorkspaceError(f"替换 src 失败：{e}") from e
    except Exception:
        # backup 存在（含悬空链接）且 src 缺失说明旧输出只剩 staging 里的备份，保留现场
        if not (
            os.path.lexists(backup) and not (src.exists() or src.is_symlink())
        ):
            shutil.rmtree(staging, ignore_errors=True)
        raise

    info["decompile"] = {
        "tool": "ilspycmd",
        "project": project,
        "source": MANAGED_DLL_REL,
        "source_sha256": dll_sha256,
        "files": count,
        "decompiled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    vj = workspace / "version.json"
    vj_tmp = workspace / "version.json.tmp"
    try:
        vj_tmp.write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(vj_tmp, vj)
    except OSError as e:
        with suppress(OSError):
            vj_tmp.unlink()
        # manifest 没更新成功就把 src 回滚到旧输出，避免源码与 manifest 不匹配
        failed_new = staging / "failed-new"
        try:
            os.replace(src, failed_new)
        except OSError as rollback_err:
            raise WorkspaceError(
                f"更新 version.json 失败：{e}；新 src 改名回 staging 也失败："
                f"{rollback_err}（新输出留在 {src}）"
            ) from e
        if src_existed:
            try:
                os.replace(backup, src)
            except OSError as restore_err:
                raise WorkspaceError(
                    f"更新 version.json 失败：{e}；恢复旧 src 也失败：{restore_err}"
                    f"（新输出在 {failed_new}，旧输出在 {backup}）"
                ) from e
        shutil.rmtree(staging, ignore_errors=True)
        raise WorkspaceError(
            f"更新 version.json 失败：{e}"
            + ("；已回滚到旧 src" if src_existed else "；新输出已清理")
        ) from e
    shutil.rmtree(staging, ignore_errors=True)
    print(f"反编译完成：{count} 个文件 -> {src}")
    return info["decompile"]
