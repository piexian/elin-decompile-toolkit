#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动定位本地安装的 Elin。

顺序：环境变量 ELIN_GAME_DIR -> 注册表/默认路径找 Steam -> libraryfolders.vdf
列库 -> 按 AppID 2135150 读 appmanifest 的 installdir -> 校验 Elin_Data/Managed/Elin.dll。

其余脚本用 `from steam_locate import find_game_dir` 拿到游戏根目录；
找不到时返回 None 并把原因写进 find_game_dir.notes，由调用方决定怎么提示。
"""
import os
import re
import subprocess
import sys

ELIN_APPID = '2135150'
ELIN_DLL = os.path.join('Elin_Data', 'Managed', 'Elin.dll')

# 候选 Steam 根目录（按平台）
_PLATFORM_DEFAULTS = {
    'win32': [os.path.expandvars(r'%ProgramFiles(x86)%\Steam'),
              os.path.expandvars(r'%ProgramFiles%\Steam')],
    'darwin': ['~/Library/Application Support/Steam'],
    'linux': ['~/.steam/steam', '~/.local/share/Steam', '~/.steam/root'],
}

notes = []          # 定位过程的线索，找不到时给用户看


def _valid_game_dir(path):
    return bool(path) and os.path.isfile(os.path.join(path, ELIN_DLL))


def _steam_roots():
    """返回候选 Steam 根目录列表（可能含不存在的）。"""
    roots = []

    env = os.environ.get('STEAM_PATH') or os.environ.get('STEAMROOT')
    if env:
        roots.append(env)
        notes.append(f'环境变量 STEAM_PATH={env}')

    # Windows 注册表（用 reg query，避免引入 pywin32 依赖）。
    # reg 的输出在中文系统上是 GBK，按 UTF-8 解会崩在读线程，所以拿原始字节自己转。
    if sys.platform == 'win32':
        for key in (r'HKLM\SOFTWARE\WOW6432Node\Valve\Steam',
                    r'HKLM\SOFTWARE\Valve\Steam',
                    r'HKCU\Software\Valve\Steam'):
            try:
                out = subprocess.run(['reg', 'query', key, '/v', 'InstallPath'],
                                     capture_output=True, timeout=10)
                for enc in ('utf-8', 'cp936'):
                    try:
                        text = out.stdout.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    text = out.stdout.decode('utf-8', 'replace')
                m = re.search(r'Reg_SZ\s+(.+)', text, re.I)
                if m:
                    p = m.group(1).strip()
                    roots.append(p)
                    notes.append(f'注册表 {key} -> {p}')
                    break
            except Exception:
                pass

    for p in _PLATFORM_DEFAULTS.get(sys.platform, []):
        roots.append(os.path.expanduser(p))
    return roots


def _vdf_libraries(steam_root):
    """解析 libraryfolders.vdf，返回所有库目录。"""
    vdf = os.path.join(steam_root, 'steamapps', 'libraryfolders.vdf')
    libs = [steam_root]
    if not os.path.isfile(vdf):
        notes.append(f'{vdf} 不存在')
        return libs
    text = open(vdf, encoding='utf-8', errors='ignore').read()
    # 只要 "path" 的值，Steam 用 \\\\ 作为分隔符
    for m in re.finditer(r'"path"\s*"([^"]+)"', text):
        libs.append(m.group(1).replace('\\\\', '\\'))
    return libs


def find_game_dir():
    """返回 Elin 游戏根目录（含 Elin_Data 的那层），找不到返回 None。"""
    # 1. 显式指定的优先
    env = os.environ.get('ELIN_GAME_DIR')
    if env:
        notes.append(f'环境变量 ELIN_GAME_DIR={env}')
        if _valid_game_dir(env):
            return env
        notes.append('  -> 缺 Elin_Data/Managed/Elin.dll，忽略')

    # 2. 脚本同级/上级目录顺带看一下（有人把工作区放在游戏目录旁边）
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (here, os.path.dirname(here), os.path.join(os.path.dirname(here), '..')):
        if _valid_game_dir(cand):
            return os.path.abspath(cand)

    # 3. Steam 库
    for root in _steam_roots():
        if not os.path.isdir(root):
            notes.append(f'Steam 目录不存在: {root}')
            continue
        for lib in _vdf_libraries(root):
            common = os.path.join(lib, 'steamapps', 'common')
            manifest = os.path.join(lib, 'steamapps', f'appmanifest_{ELIN_APPID}.acf')
            installdir = None
            if os.path.isfile(manifest):
                try:
                    txt = open(manifest, encoding='utf-8', errors='ignore').read()
                    m = re.search(r'"installdir"\s*"([^"]+)"', txt)
                    if m:
                        installdir = m.group(1)
                except OSError:
                    pass
            for cand in ([installdir] if installdir else []) + ['Elin']:
                p = os.path.join(common, cand)
                if _valid_game_dir(p):
                    return p
            notes.append(f'{lib} 里没有可用的 Elin（manifest={os.path.isfile(manifest)}）')
    return None


def lang_cn_dir(game_dir):
    """官方简中语言包的 CN 目录。"""
    return os.path.join(game_dir, 'Package', '_Lang_Chinese', 'Lang', 'CN')


if __name__ == '__main__':
    g = find_game_dir()
    if g:
        print('找到 Elin:', g)
        print('语言包:', lang_cn_dir(g), '存在' if os.path.isdir(lang_cn_dir(g)) else '不存在')
    else:
        print('未找到 Elin。尝试过的线索：')
        for n in notes:
            print('  ', n)
        sys.exit(1)
