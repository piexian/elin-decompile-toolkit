"""sprites：按游戏「创建替换图」的图集矩形逻辑裁剪角色/物件像素图。

矩形规则复刻自源码 TextureData.CreateReplace（Elin.decompiled.cs 64994）：
  index = row*100 + col（row 自顶向下），x = col*tileW，y = row*tileH（PIL 顶左坐标，
  源码里的 tex.height-row*tileH-h 是 Unity 自底向上坐标，换算后等价），
  条带 = tileW×sizeX、tileH×sizeY，最后按 alpha 包围盒紧裁。
  tileW = 图集宽 ÷ 渲染 pass 的 tiling（65122），实测：objs=64、objs_S=32、
  角色系=128。角色：chara→objs_C(32列,1行)；chara_L、chara_LW→objs_CL(32列,2行，
  源码 65077/65098：passCharaL 与 passCharaLW 共用 objs_CL)；chara_LL→objs_CLL(16列,3行)。
  chara_L 系精灵会向下跨行（锚点格常只含精灵顶部几像素），靠跨度覆盖后紧裁。
  物件（things）：obj→objs(64px)、obj_S→objs_S(32px)，跨度=物品 W×H 占地格数，
  渲染数据带 tall 时高度按 2 格起裁；物件默认输出整格，加 --trim 才按 alpha 紧裁。
  obj_L/obj_SS 等未验证，工具会拒绝并提示。

只支持已验证的 atlas family（ATLAS / THINGS 两张表）。
"""

import json
from pathlib import Path

from .errors import ElinToolError, ExitCode
from .game_assets import find_game_dir

PILLOW_URL = "https://pypi.org/project/Pillow/"

TILE = 128
ATLAS = {  # 渲染数据 → (图集文件, 列数, 条带行数)
    "chara": ("objs_C.png", 32, 1),
    "chara_L": ("objs_CL.png", 32, 2),
    "chara_LW": ("objs_CL.png", 32, 2),
    "chara_LL": ("objs_CLL.png", 16, 3),
}
THINGS = {  # 物件渲染数据前缀 → (图集文件, 格子px)
    "obj": ("objs.png", 64),
    "obj_S": ("objs_S.png", 32),
}
ATLAS_DIR = "Package/_Elona/Texture"


class SpritesError(ElinToolError):
    """精灵裁剪失败（缺 Pillow、未知 id、不支持的渲染数据）。"""

    exit_code = ExitCode.USAGE


def _load_pil():
    try:
        from PIL import Image

        return Image
    except ImportError as e:
        raise SpritesError(f"需要 Pillow：pip install Pillow（{PILLOW_URL}）") from e


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise SpritesError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise SpritesError(f"JSON 损坏 {path}：{e}") from e


def _read_jsonl(path: Path) -> list:
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as e:
        raise SpritesError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise SpritesError(f"JSONL 损坏 {path}：{e}") from e


def _camel(cid: str) -> str:
    return "".join(w.capitalize() for w in cid.split("_"))


def _open_atlas(Image, gdir: Path, atlas_file: str):
    """打开图集并验证为 RGBA 位图，OSError/解码错误转 SpritesError。"""
    path = gdir / ATLAS_DIR / atlas_file
    try:
        atlas = Image.open(path).convert("RGBA")
    except FileNotFoundError as e:
        raise SpritesError(f"图集文件缺失：{path}") from e
    except OSError as e:
        raise SpritesError(f"图集读取或解码失败 {path}：{e}") from e
    if atlas.width <= 0 or atlas.height <= 0:
        raise SpritesError(f"图集尺寸异常：{path} ({atlas.width}x{atlas.height})")
    return atlas


def _bbox_strip(Image, strip, cid: str):
    """按 alpha 包围盒紧裁；完全透明时明确报错。"""
    bbox = strip.getbbox()
    if bbox is None or bbox[2] - bbox[0] <= 0 or bbox[3] - bbox[1] <= 0:
        raise SpritesError(
            f"{cid} 的图块区域完全透明（图集格没有像素），请核对该 id 的图块索引"
        )
    return strip.crop(bbox)


def sprites(workspace: Path, ids: list, game, trim, snow, tile, outdir, name) -> int:
    """裁剪角色/物品精灵到 reports/sprites（或 --outdir），返回退出码语义的错误。"""
    if name and len(ids) > 1:
        raise SpritesError("--name 只能配合单个 id 使用，多个 id 会互相覆盖输出文件")
    if tile is not None and len(ids) > 1:
        raise SpritesError("--tile 只能配合单个 id 使用")
    if tile is not None and tile < 0:
        raise SpritesError(f"--tile 不能是负数：{tile}")
    if outdir is not None:
        od = Path(outdir)
        if od.is_symlink() or (od.exists() and not od.is_dir()):
            raise SpritesError(
                f"输出目录已存在且不是目录或是指向别处的符号链接，拒绝操作：{od}"
            )
    Image = _load_pil()
    data = workspace / "data"
    charas = {c["id"]: c for c in _read_jsonl(data / "charas_full.jsonl")}
    things = {t["id"]: t for t in _read_jsonl(data / "things_full.jsonl")}
    lang = _load_json(data / "lang" / "Chara.json")
    lang_t = _load_json(data / "lang" / "Thing.json")

    if game:
        gdir = find_game_dir(game)
    else:
        gdir = find_game_dir(None)  # ELIN_GAME_DIR / Steam 发现

    default_root = Path(outdir) if outdir else workspace / "reports" / "sprites"
    if default_root.is_symlink() or (default_root.exists() and not default_root.is_dir()):
        raise SpritesError(
            f"输出路径已存在且不是目录或是指向别处的符号链接，拒绝操作：{default_root}"
        )
    n = 0
    for cid in ids:
        c = charas.get(cid)
        if c:
            rd = c["_idRenderData"]
            if rd not in ATLAS:
                raise SpritesError(f"渲染数据 {rd!r} 不在已验证列表（{', '.join(ATLAS)}）")
            atlas_file, cols, span = ATLAS[rd]
            if tile is not None:
                idx = tile
            elif snow:
                arr = c.get("_tiles_snow") or c.get("tiles_snow")
                if not arr:
                    raise SpritesError(f"{cid} 没有冬装图块（tiles_snow 为空）")
                idx = arr[0]
            else:
                idx = (c["_tiles"] or c["tiles"])[0]
            if idx < 0:
                raise SpritesError(f"{cid} 的图块索引为负数：{idx}（数据异常）")
            col, row = idx % cols, idx // cols
            atlas = _open_atlas(Image, gdir, atlas_file)
            rows_n = atlas.height // TILE
            if row >= rows_n or col >= atlas.width // TILE:
                raise SpritesError(
                    f"{cid} 图块索引 {idx} 超出图集 {atlas_file}（{rows_n} 行）范围"
                )
            span = min(span, rows_n - row)
            strip = atlas.crop(
                (col * TILE, row * TILE, (col + 1) * TILE, (row + span) * TILE)
            )
            s = _bbox_strip(Image, strip, cid)
            zh = (lang.get(cid) or {}).get("name") or ""
            zh = zh if zh and not zh.startswith("*") else cid
            target = default_root / "characters" / zh if not outdir else default_root
            out_name = name or _camel(cid) + ("Snow" if snow else "")
        else:
            t = things.get(cid)
            if not t:
                raise SpritesError(f"未知 id: {cid}")
            rd = t["_idRenderData"]
            family = rd.split(" ")[0]
            if family not in THINGS:
                raise SpritesError(
                    f"渲染数据 {rd!r} 暂不支持（obj_L/obj_SS 等请手工核对偏移；"
                    f"已验证：{', '.join(THINGS)}）"
                )
            atlas_file, cell = THINGS[family]
            idx = (t["tiles"] or [0])[0]
            if idx < 0:
                raise SpritesError(f"{cid} 的图块索引为负数：{idx}（数据异常）")
            col, row = idx % 100, idx // 100
            sx = max(int(t.get("W") or 1), 1)
            sy = max(int(t.get("H") or 1), 2 if "tall" in rd else 1)
            atlas = _open_atlas(Image, gdir, atlas_file)
            if col >= atlas.width // cell or row >= atlas.height // cell:
                raise SpritesError(
                    f"{cid} 图块索引 {idx} 超出图集 {atlas_file} 范围"
                )
            sx = min(sx, atlas.width // cell - col)
            sy = min(sy, atlas.height // cell - row)
            if sx <= 0 or sy <= 0:
                raise SpritesError(
                    f"{cid} 的占地 {t.get('W')}x{t.get('H')} 超出图集 {atlas_file} 剩余空间"
                )
            strip = atlas.crop(
                (col * cell, row * cell, (col + sx) * cell, (row + sy) * cell)
            )
            s = _bbox_strip(Image, strip, cid) if trim else strip.copy()
            zh = (lang_t.get(cid) or {}).get("name") or ""
            zh = zh if zh and not zh.startswith("*") else cid
            target = default_root / "objects" / zh if not outdir else default_root
            out_name = name or "Elin_Icon_" + _camel(cid)
        try:
            target.mkdir(parents=True, exist_ok=True)
            s.save(target / (out_name + ".png"))
            s.resize((s.width * 8, s.height * 8), Image.NEAREST).save(
                target / (out_name + "_8x.png")
            )
        except OSError as e:
            raise SpritesError(f"写出精灵图失败 {target}/{out_name}.png：{e}") from e
        print("OK", cid, rd, atlas_file, f"r{row}c{col}", "->", out_name, s.size)
        n += 1
    print(f"输出: {default_root}（{n} 个 id，附 _8x 预览）")
    return 0
