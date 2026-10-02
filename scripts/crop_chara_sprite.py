#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按游戏「创建替换图」的图集矩形逻辑裁剪角色/物件像素图。

矩形规则复刻自源码 TextureData.CreateReplace（Elin.decompiled.cs 64994）：
  index = row*100 + col（row 自顶向下），x = col*tileW，y = row*tileH（PIL 顶左坐标，
  源码里的 tex.height-row*tileH-h 是 Unity 自底向上坐标，换算后等价），
  条带 = tileW×sizeX、tileH×sizeY，最后按 alpha 包围盒紧裁。
  tileW = 图集宽 ÷ 渲染 pass 的 tiling（65122），实测：objs=64、objs_S=32、
  角色系=128。角色：chara→objs_C(32列,1行)；chara_L、chara_LW→objs_CL(32列,2行，
  源码 65077/65098：passCharaL 与 passCharaLW 共用 objs_CL)；chara_LL→objs_CLL(16列,3行)。
  chara_L 系精灵会向下跨行（锚点格常只含精灵顶部几像素），靠跨度覆盖后紧裁。
  物件（things）：obj→objs(64px)、obj_S→objs_S(32px)，跨度=物品 W×H 占地格数，
  渲染数据带 tall 时高度按 2 格起裁；物件默认输出整格（与已发布物品图标惯例一致），
  加 --trim 才按 alpha 紧裁；obj_L/obj_SS 等未验证，工具会拒绝并提示。

用法: python crop_chara_sprite.py <id> [id ...] [--outdir 目录] [--name 文件名]
  id 可以是角色 id（charas_full.jsonl）或物品 id（things_full.jsonl）。
输出: 默认 drafts/characters/<官方中文名>/Elin_Npc_Sprite_<大驼峰id>.png（+ _8x 预览）
  物品输出到 drafts/objects/<官方中文名>/Elin_Icon_<大驼峰id>.png。
"""
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILE = 128
ATLAS = {  # 渲染数据 → (图集文件, 列数, 条带行数)
    'chara': ('objs_C.png', 32, 1),
    'chara_L': ('objs_CL.png', 32, 2),
    'chara_LW': ('objs_CL.png', 32, 2),
    'chara_LL': ('objs_CLL.png', 16, 3),
}
THINGS = {  # 物件渲染数据前缀 → (图集文件, 格子px)
    'obj': ('objs.png', 64),
    'obj_S': ('objs_S.png', 32),
}


def game_dir():
    env = os.environ.get('ELIN_GAME_DIR')
    if env:
        return env
    sys.path.insert(0, ROOT + os.sep + 'tools')
    from steam_locate import find_game_dir
    g = find_game_dir()
    if not g:
        raise SystemExit('找不到 Elin 安装目录：请设 ELIN_GAME_DIR')
    return g


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    outdir = None
    name = None
    trim = '--trim' in sys.argv
    for a in sys.argv[1:]:
        if a.startswith('--outdir='):
            outdir = a.split('=', 1)[1]
        elif a.startswith('--name='):
            name = a.split('=', 1)[1]
    if not args:
        raise SystemExit(__doc__)

    charas = {}
    with open(os.path.join(ROOT, 'data', 'charas_full.jsonl'), encoding='utf-8') as f:
        for line in f:
            c = json.loads(line)
            charas[c['id']] = c
    things = {}
    with open(os.path.join(ROOT, 'data', 'things_full.jsonl'), encoding='utf-8') as f:
        for line in f:
            t = json.loads(line)
            things[t['id']] = t
    lang = json.load(open(os.path.join(ROOT, 'data', 'lang', 'Chara.json'), encoding='utf-8'))
    lang_t = json.load(open(os.path.join(ROOT, 'data', 'lang', 'Thing.json'), encoding='utf-8'))
    gdir = game_dir()

    for cid in args:
        c = charas.get(cid)
        if c:
            rd = c['_idRenderData']
            atlas_file, cols, span = ATLAS[rd]
            idx = (c['_tiles'] or c['tiles'])[0]
            col, row = idx % cols, idx // cols
            atlas = Image.open(os.path.join(gdir, 'Package', '_Elona', 'Texture', atlas_file)).convert('RGBA')
            span = min(span, atlas.height // TILE - row)
            strip = atlas.crop((col * TILE, row * TILE, (col + 1) * TILE, (row + span) * TILE))
            s = strip.crop(strip.getbbox())
            if outdir is None:
                zh = (lang.get(cid) or {}).get('name') or ''
                zh = zh if zh and not zh.startswith('*') else cid
                outdir = os.path.join(ROOT, 'drafts', 'characters', zh)
            if name is None:
                name = 'Elin_Npc_Sprite_' + ''.join(w.capitalize() for w in cid.split('_'))
        else:
            t = things.get(cid)
            if not t:
                raise SystemExit('未知 id: ' + cid)
            rd = t['_idRenderData']
            family = rd.split(' ')[0]
            if family not in THINGS:
                raise SystemExit('渲染数据 %r 暂不支持（obj_L/obj_SS 等请手工核对偏移）' % rd)
            atlas_file, cell = THINGS[family]
            idx = (t['tiles'] or [0])[0]
            col, row = idx % 100, idx // 100
            sx = max(int(t.get('W') or 1), 1)
            sy = max(int(t.get('H') or 1), 2 if 'tall' in rd else 1)
            atlas = Image.open(os.path.join(gdir, 'Package', '_Elona', 'Texture', atlas_file)).convert('RGBA')
            sx = min(sx, atlas.width // cell - col)
            sy = min(sy, atlas.height // cell - row)
            strip = atlas.crop((col * cell, row * cell, (col + sx) * cell, (row + sy) * cell))
            s = strip if trim else strip.crop((0, 0, strip.width, strip.height))
            if outdir is None:
                zh = (lang_t.get(cid) or {}).get('name') or ''
                zh = zh if zh and not zh.startswith('*') else cid
                outdir = os.path.join(ROOT, 'drafts', 'objects', zh)
            if name is None:
                name = 'Elin_Icon_' + ''.join(w.capitalize() for w in cid.split('_'))
        os.makedirs(outdir, exist_ok=True)
        s.save(os.path.join(outdir, name + '.png'))
        s.resize((s.width * 8, s.height * 8), Image.NEAREST).save(os.path.join(outdir, name + '_8x.png'))
        print('OK', cid, rd, atlas_file, 'r%dc%d' % (row, col), '->', name, s.size)


if __name__ == '__main__':
    main()
