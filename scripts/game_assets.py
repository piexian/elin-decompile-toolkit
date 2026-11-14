"""游戏目录、sharedassets0.assets 与简中语言包定位。"""
import os
import re
import struct
import sys
from pathlib import Path

from .errors import PathNotFoundError

ASSETS_NAME = "sharedassets0.assets"
LANG_CN_REL = "Package/_Lang_Chinese/Lang/CN"
ELIN_APPID = "2135150"
ELIN_DLL = Path("Elin_Data/Managed/Elin.dll")

# 各平台的候选 Steam 根目录
PLATFORM_STEAM_ROOTS = {
    "win32": [r"%ProgramFiles(x86)%\Steam", r"%ProgramFiles%\Steam"],
    "darwin": ["~/Library/Application Support/Steam"],
    "linux": ["~/.steam/steam", "~/.local/share/Steam", "~/.steam/root"],
}


def _valid_game_dir(path: Path) -> bool:
    """目录下有 Elin_Data/Managed/Elin.dll 才算有效游戏根。"""
    return path.is_dir() and (path / ELIN_DLL).is_file()


def _windows_registry_steam() -> list[Path]:
    """从 Windows 注册表读 Steam 安装目录（用 reg query，避免 pywin32 依赖）。"""
    import subprocess

    roots = []
    for key in (
        r"HKLM\SOFTWARE\WOW6432Node\Valve\Steam",
        r"HKLM\SOFTWARE\Valve\Steam",
        r"HKCU\Software\Valve\Steam",
    ):
        try:
            out = subprocess.run(
                ["reg", "query", key, "/v", "InstallPath"],
                capture_output=True,
                timeout=10,
            )
        except OSError:
            return roots
        for enc in ("utf-8", "cp936"):
            try:
                text = out.stdout.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = out.stdout.decode("utf-8", "replace")
        m = re.search(r"Reg_SZ\s+(.+)", text, re.I)
        if m:
            roots.append(Path(m.group(1).strip()))
            break
    return roots


def _steam_roots() -> list[Path]:
    """候选 Steam 根目录：STEAM_PATH/STEAMROOT、Windows 注册表、平台默认路径。"""
    roots = []
    env = os.environ.get("STEAM_PATH") or os.environ.get("STEAMROOT")
    if env:
        roots.append(Path(env))
    if sys.platform == "win32":
        roots.extend(_windows_registry_steam())
    for p in PLATFORM_STEAM_ROOTS.get(sys.platform, []):
        roots.append(Path(os.path.expandvars(os.path.expanduser(p))))
    return roots


def _vdf_libraries(steam_root: Path) -> list[Path]:
    """解析 libraryfolders.vdf，返回 Steam 根本身与全部库目录。"""
    libs = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf.is_file():
        return libs
    text = vdf.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r'"path"\s*"([^"]+)"', text):
        libs.append(Path(m.group(1).replace("\\\\", "\\")))
    return libs


def _steam_game_candidates() -> list[Path]:
    """按 Steam 库的 appmanifest_2135150.acf 生成候选游戏目录。"""
    candidates = []
    for root in _steam_roots():
        if not root.is_dir():
            continue
        for lib in _vdf_libraries(root):
            common = lib / "steamapps" / "common"
            manifest = lib / "steamapps" / f"appmanifest_{ELIN_APPID}.acf"
            installdir = None
            if manifest.is_file():
                m = re.search(
                    r'"installdir"\s*"([^"]+)"',
                    manifest.read_text(encoding="utf-8", errors="ignore"),
                )
                if m:
                    installdir = m.group(1)
            for name in ([installdir] if installdir else []) + ["Elin"]:
                candidates.append(common / name)
    return candidates


def find_game_dir(explicit: Path | None = None) -> Path:
    """定位游戏根目录：显式 --game > ELIN_GAME_DIR > Steam 库自动发现。"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("ELIN_GAME_DIR")
    if env:
        candidates.append(Path(env))
    candidates.extend(_steam_game_candidates())
    for cand in candidates:
        if _valid_game_dir(cand):
            return cand
    raise PathNotFoundError(
        "找不到 Elin 游戏目录（需含 Elin_Data/Managed/Elin.dll）："
        "用 --game 指定，或设置 ELIN_GAME_DIR；Steam 库里也没有找到"
    )

def resolve_assets(game_dir: Path) -> Path:
    """接受游戏根目录或 Elin_Data 目录，返回 sharedassets0.assets 路径。"""
    for cand in (game_dir, game_dir / "Elin_Data"):
        p = cand / ASSETS_NAME
        if p.is_file():
            return p
    raise PathNotFoundError(f"找不到 {ASSETS_NAME}（实际得到 {game_dir}）")


def read_assets(game_dir: Path) -> bytes:
    """读取 sharedassets0.assets 全量字节。"""
    path = resolve_assets(game_dir)
    try:
        return path.read_bytes()
    except OSError as e:
        raise PathNotFoundError(f"读取 {path} 失败：{e}") from e


def lang_cn_dir(game_dir: Path) -> Path:
    """官方简中语言包目录。"""
    p = game_dir / LANG_CN_REL
    if not p.is_dir():
        raise PathNotFoundError(f"简中语言包目录不存在：{p}")
    return p


def iter_table_headers(data: bytes, name: str) -> list[int]:
    """扫描 len32+name+\\0 的 Source 表对象头，返回候选解析起点。"""
    pat = re.compile(
        re.escape(struct.pack("<i", len(name))) + re.escape(name.encode()) + b"\x00"
    )
    return [m.end() + 3 for m in pat.finditer(data)]
