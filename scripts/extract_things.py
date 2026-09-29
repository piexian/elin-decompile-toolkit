#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Elin 的 sharedassets0.assets 提取物品(SourceThing)行数据。
用法: python extract_things.py [游戏目录或Elin_Data目录] <输出目录>
      不传游戏目录时自动从 Steam 定位（也可用环境变量 ELIN_GAME_DIR 指定）。
产出:
  things.jsonl   每行一个物品: {name_en, name_jp, defMat, recipe_key, components, factory, extra, id, traits, filters, tokens}
  recipes.json   有制作配方的物品: {id, name_en, components, factory}
  materials.json 材质表: [{id, key, jp, en, decay...}]
原理: Unity 序列化的 length-prefix 字符串流; 行首是 [英文名][日文名] 两个字符串。
字段布局经反编译+多行对齐确认: name, name_JP, _, _, renderData, tileType, defMat, _,
  recipeKey, fieldC?, _, components[], factory[], extra[], ...ints..., id, ..., category?, ...
  ...elements(int对)..., filter[], trait[], ... unit 等。
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from steam_locate import find_game_dir


def is_str_at(data, p):
    if p + 4 > len(data):
        return None
    ln = struct.unpack('<i', data[p:p + 4])[0]
    if 0 < ln < 100 and p + 4 + ln <= len(data):
        s = data[p + 4:p + 4 + ln]
        try:
            t = s.decode('utf-8')
            if t and all(c.isprintable() for c in t):
                return t, (p + 4 + ln + 3) & ~3
        except UnicodeDecodeError:
            pass
    return None


def walk_tokens(data, start, end):
    """把 [start,end) 区域走查成 token 序列: ('s', str) 或 ('i', int)"""
    toks = []
    p = start
    while p < end:
        r = is_str_at(data, p)
        if r:
            toks.append(('s', r[0]))
            p = r[1]
        else:
            toks.append(('i', struct.unpack('<i', data[p:p + 4])[0]))
            p += 4
    return toks


def find_thing_region(data):
    """定位 SourceThing 区域: 用已知物品名锚定"""
    anchors = [b'\x06\x00\x00\x00cheese', b'\x06\x00\x00\x00burger']
    pts = []
    for a in anchors:
        m = re.search(re.escape(a), data)
        if m:
            pts.append(m.start())
    return (min(pts) - 4000000, max(pts) + 4000000) if pts else (540000000, 560000000)


def load_known_names(outdir):
    """官方语言包里的全部物品英文名/日文名, 用于精确识别行首"""
    names = set()
    for fn in ('Thing.json', 'ThingV.json'):
        p = os.path.join(outdir, 'lang', fn)
        if os.path.exists(p):
            for row in json.load(open(p, encoding='utf-8')).values():
                for k in ('name_EN', 'name', 'name_JP'):
                    v = row.get(k)
                    if v:
                        names.add(v)
    return names


def extract_things(data, lo, hi, known_names):
    # 行首 = [len][英文名][len][日文名][int][int]...; 英文名必须在官方译名表中,
    # 且日文名后必须紧跟两个 int(防止把成分表里的 'dough' 之类误判为行首)
    starts = []
    p = lo
    while p < hi - 12:
        r1 = is_str_at(data, p)
        if r1 and r1[0] in known_names:
            r2 = is_str_at(data, r1[1])
            if (r2 and any(ord(c) > 0x7f for c in r2[0])
                    and is_str_at(data, r2[1]) is None and is_str_at(data, r2[1] + 4) is None):
                starts.append((p, r1[0], r2[0]))
                p = r1[1]
                continue
        p += 4
    rows = []
    for idx, (off, name_en, name_jp) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else off + 800
        if end - off > 1400:
            end = off + 1400
        toks = walk_tokens(data, off, end)
        rows.append({'offset': off, 'name_en': name_en, 'name_jp': name_jp, 'tokens': toks})
    return rows


def interpret(row):
    """按确认的字段布局提取关键字段; 失败时保留原始 tokens"""
    t = row['tokens']
    out = {'name_en': row['name_en'], 'name_jp': row['name_jp']}
    strs = [v for k, v in t if k == 's']
    # 布局: [0]=name_en [1]=name_jp [2]=renderData [3]=tileType?(可缺) [4]=defMat [5]=recipeKey [6]=fieldC(可缺) 之后是数组区
    # 数组区定位: 找到第一个 ('i', n) 后紧跟 n 个 's' 的位置
    def read_array(i):
        if i < len(t) and t[i][0] == 'i' and 0 < t[i][1] <= 12:
            n = t[i][1]
            if all(j < len(t) and t[j][0] == 's' for j in range(i + 1, i + 1 + n)):
                return [t[j][1] for j in range(i + 1, i + 1 + n)], i + 1 + n
        return None, i
    # 顺序扫描: 跳过头部单字符串, 直到遇到第一个合法数组
    i = 0
    head = []
    while i < len(t):
        if t[i][0] == 's':
            head.append(t[i][1])
            i += 1
        else:
            arr, ni = read_array(i)
            if arr is not None and i + 1 < len(t):
                # 验证是数组: 前一个 token 是 int 且后面确实以字符串开始
                break
            i += 1
    arr1, i = read_array(i) if i < len(t) else (None, i)
    # 找 factory: 跳过中间 int, 读下一个数组
    j = i
    while j < len(t) and t[j][0] == 'i':
        j += 1
    arr2 = None
    if j > i and j - 1 < len(t):
        # factory 的 count 是 int 序列里最后一个合法数组头
        for k in range(i, min(j, i + 4)):
            a2, _ = read_array(k)
            if a2 is not None:
                arr2 = a2
    out['head_strings'] = head
    out['components'] = arr1
    out['factory'] = arr2
    # id: 数组区之后第一个"像id"的字符串
    tail = [v for k, v in t[len(head):] if k == 's']
    out['tail_strings'] = tail
    return out


def resolve_assets(data_dir):
    """接受游戏根目录或 Elin_Data 目录，返回 sharedassets0.assets 路径。
    不传目录时自动从 Steam 定位。"""
    if not data_dir:
        data_dir = find_game_dir()
        if not data_dir:
            raise SystemExit('找不到 Elin 安装目录：请装在 Steam 库里，或用环境变量 '
                             'ELIN_GAME_DIR / 第一个参数指定游戏根目录')
        print(f'自动定位游戏: {data_dir}')
    for cand in (data_dir, os.path.join(data_dir, 'Elin_Data')):
        p = os.path.join(cand, 'sharedassets0.assets')
        if os.path.exists(p):
            return p
    raise SystemExit(f'找不到 sharedassets0.assets：请传游戏根目录或 Elin_Data 目录（实际得到 {data_dir}）')


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        data_dir, outdir = args[0], args[1]
    elif len(args) == 1:
        data_dir, outdir = None, args[0]
    else:
        raise SystemExit(__doc__)
    os.makedirs(outdir, exist_ok=True)
    data = open(resolve_assets(data_dir), 'rb').read()
    lo, hi = find_thing_region(data)
    known = load_known_names(outdir)
    print(f'known names: {len(known)}')
    if not known:
        print('  !! 语言包为空：先跑 lang_xlsx_to_json.py 把 Thing.json 放进 <输出目录>/lang/，'
              '否则行首识别没有依据，会静默产出 0 行')
    rows = extract_things(data, lo, hi, known)
    with open(os.path.join(outdir, 'things.jsonl'), 'w', encoding='utf-8') as f:
        for r in rows:
            info = interpret(r)
            f.write(json.dumps(info, ensure_ascii=False) + '\n')
    recipes = []
    for r in rows:
        info = interpret(r)
        comps = info.get('components')
        if comps and comps != ['-'] and info.get('factory'):
            recipes.append({'name_en': info['name_en'], 'name_jp': info['name_jp'],
                            'components': comps, 'factory': info['factory'],
                            'tail': info.get('tail_strings', [])[:4]})
    with open(os.path.join(outdir, 'recipes.json'), 'w', encoding='utf-8') as f:
        json.dump(recipes, f, ensure_ascii=False, indent=1)
    print(f'things: {len(rows)} rows, recipes: {len(recipes)}')


if __name__ == '__main__':
    main()
