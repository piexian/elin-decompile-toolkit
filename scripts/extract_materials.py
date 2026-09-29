#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取 SourceMaterial 材质表。
用法: python extract_materials.py [游戏目录或Elin_Data目录] <工作区data目录>
      不传游戏目录时自动从 Steam 定位（也可用环境变量 ELIN_GAME_DIR 指定）。
产出 materials.json: { "材质key": {id, jp, en, cn, decay, ints} }
布局(经对齐验证, 用 hardness=1/tier 等交叉确认过 meat/process 两行):
  [id][id][alias][name_JP][name][category][tag[]][thing][goods[]][minerals[]][decal][decay]...
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_things import is_str_at


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        data_dir, outdir = args[0], args[1]
    elif len(args) == 1:
        data_dir, outdir = None, args[0]
    else:
        raise SystemExit(__doc__)
    from extract_things import resolve_assets
    data = open(resolve_assets(data_dir), 'rb').read()
    # 材质区: 用 'process' 材质锚定 (id=94)
    anchor = data.find(b'\x07\x00\x00\x00process\x0b\x00\x00\x00')
    if anchor < 0:
        anchor = 546640000
    lo, hi = anchor - 300000, anchor + 300000
    lang = {}
    lp = os.path.join(outdir, 'lang', 'Material.json')
    if os.path.exists(lp):
        lang = json.load(open(lp, encoding='utf-8'))
    cn_by_id = {k: v.get('name', '') for k, v in lang.items()}
    mats = {}
    p = lo
    while p < hi - 16:
        a = struct.unpack('<i', data[p:p + 4])[0]
        b = struct.unpack('<i', data[p + 4:p + 8])[0]
        r = is_str_at(data, p + 8)
        if a == b and 0 < a < 300 and r and len(r[0]) >= 2 and r[0].replace('_', '').isalpha():
            key = r[0]
            q = r[1]
            jp = en = cat = ''
            r2 = is_str_at(data, q)
            if r2 and any(ord(c) > 0x7f for c in r2[0]):
                jp = r2[0]
                r3 = is_str_at(data, r2[1])
                if r3:
                    en = r3[0]
                    r4 = is_str_at(data, r3[1])
                    if r4:
                        cat = r4[0]
                        q = r4[1]
            # 继续走查收集 int, 按布局 decal/decay 在 goods/minerals 两个数组之后
            toks = []
            steps = 0
            while steps < 40:
                rr = is_str_at(data, q)
                if rr:
                    toks.append(('s', rr[0]))
                    q = rr[1]
                else:
                    toks.append(('i', struct.unpack('<i', data[q:q + 4])[0]))
                    q += 4
                steps += 1
                # 下一个材质行的开始则停
                if q + 16 < len(data):
                    a2 = struct.unpack('<i', data[q:q + 4])[0]
                    b2 = struct.unpack('<i', data[q + 4:q + 8])[0]
                    rr2 = is_str_at(data, q + 8)
                    if a2 == b2 and 0 < a2 < 300 and rr2 and rr2[0].replace('_', '').isalpha():
                        break
            mats[key] = {'id': a, 'jp': jp, 'en': en, 'category': cat,
                         'cn': cn_by_id.get(str(a), ''), 'tokens': toks}
            p = q
        else:
            p += 4
    out = os.path.join(outdir, 'materials.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(mats, f, ensure_ascii=False, indent=1)
    print(f'materials: {len(mats)}')
    for k in ('meat', 'process'):
        if k in mats:
            print(k, '→', mats[k]['id'], mats[k]['cn'], mats[k]['jp'])


if __name__ == '__main__':
    main()
