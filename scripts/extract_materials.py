#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Elin 的 sharedassets0.assets 提取材质表(SourceMaterial)行数据。

用法: python extract_materials.py [游戏目录或Elin_Data目录] <输出目录>
      不传游戏目录时自动从 Steam 定位（也可用环境变量 ELIN_GAME_DIR 指定）。
产出:
  materials.jsonl  每行一个材质: {id, alias, cn, prefix_cn, category, hardness,
                   tier, weight, value, quality, atk, dmg, dv, pv, dice, bits,
                   elements, altName, fireproof, acidproof, ...}
  materials.json   旧格式兼容版 {key: {id, jp, en, cn}} 供 tools/lookup.py 使用

原理: SourceMaterial.Row 的 Unity 序列化布局（声明序，4 字节对齐）:
  [_index][id][alias][name_JP][name][category][tag[]][thing][goods[]][minerals[]]
  [decal][decay][grass][defFloor][defBlock][edge][ramp][idSound][soundFoot]
  [hardness][groups[]][tier][chance][weight][value][quality][atk][dmg][dv][pv]
  [dice][bits[]][elements:i32[]][altName[]][altName_JP[]][matColor:4f][altColor:4f]
  elementMap 是 Dictionary，Unity 不序列化。行间可能有 1 个 int 的 pad，
  链式解析按 [_index 连续递增] 自动对齐。首行锚点 [_index][id=1]'plain'。
CN 名与词缀取自 data/lang/Material.json（name / altName 列）。
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from steam_locate import find_game_dir

FIELDS = [
    ('_index', 'i'), ('id', 'i'), ('alias', 's'), ('name_JP', 's'), ('name', 's'),
    ('category', 's'), ('tag', 'sa'), ('thing', 's'), ('goods', 'sa'),
    ('minerals', 'sa'), ('decal', 'i'), ('decay', 'i'), ('grass', 'i'),
    ('defFloor', 'i'), ('defBlock', 'i'), ('edge', 'i'), ('ramp', 'i'),
    ('idSound', 's'), ('soundFoot', 's'), ('hardness', 'i'), ('groups', 'sa'),
    ('tier', 'i'), ('chance', 'i'), ('weight', 'i'), ('value', 'i'),
    ('quality', 'i'), ('atk', 'i'), ('dmg', 'i'), ('dv', 'i'), ('pv', 'i'),
    ('dice', 'i'), ('bits', 'sa'), ('elements', 'ia'), ('altName', 'sa'),
    ('altName_JP', 'sa'),
]
# 注意: 反编译里的 matColor/altColor (Color) 不在序列化流里，实测行尾即 altName_JP。


def align(p):
    return (p + 3) & ~3


def read_string(data, p):
    if p + 4 > len(data):
        return None, p
    n = struct.unpack('<i', data[p:p + 4])[0]
    if n < 0 or n > 4096 or p + 4 + n > len(data):
        return None, p
    try:
        s = data[p + 4:p + 4 + n].decode('utf-8')
    except UnicodeDecodeError:
        return None, p
    return s, align(p + 4 + n)


def read_int_array(data, p):
    if p + 4 > len(data):
        return None, p
    n = struct.unpack('<i', data[p:p + 4])[0]
    if n < 0 or n > 64 or p + 4 + 4 * n > len(data):
        return None, p
    vals = list(struct.unpack('<%di' % n, data[p + 4:p + 4 + 4 * n])) if n else []
    return vals, align(p + 4 + 4 * n)


def read_str_array(data, p):
    if p + 4 > len(data):
        return None, p
    n = struct.unpack('<i', data[p:p + 4])[0]
    if n < 0 or n > 64 or p + 4 > len(data):
        return None, p
    p += 4
    vals = []
    for _ in range(n):
        s, p = read_string(data, p)
        if s is None:
            return None, p
        vals.append(s)
    return vals, align(p)


def parse_row(data, off):
    p = off
    row = {}
    for name, typ in FIELDS:
        if typ == 'i':
            if p + 4 > len(data):
                return None
            row[name] = struct.unpack('<i', data[p:p + 4])[0]
            p += 4
        elif typ == '4f':
            if p + 16 > len(data):
                return None
            row[name] = struct.unpack('<4f', data[p:p + 16])
            p += 16
        elif typ == 's':
            s, p = read_string(data, p)
            if s is None:
                return None
            row[name] = s
        else:
            fn = read_int_array if typ == 'ia' else read_str_array
            vals, p = fn(data, p)
            if vals is None:
                return None
            row[name] = vals
    return row, p


def find_table_start(data):
    """材质表首行：锚 process(id=94) 行，向前回溯到 _index==1。
    不能直接锚 'plain'：地区表(SourceZone)也有同名 plain 行。"""
    i = 0
    while True:
        i = data.find(b'\x07\x00\x00\x00process', i + 1)
        if i < 0:
            return None
        a, b = struct.unpack('<ii', data[i - 8:i])
        if b != 94 or a != 94:
            continue
        cur = i - 8
        starts = []
        while cur > 0 and len(starts) < 200:
            hit = None
            for back in range(4, 1024, 4):
                off = cur - back
                if off < 0:
                    break
                got = parse_row(data, off)
                if got:
                    row, endp = got
                    if endp == cur:
                        hit = (off, row)
                        break
            if not hit:
                break
            starts.append(hit)
            cur = hit[0]
            if hit[1]['_index'] <= 0:
                return cur
        return None


def chain_parse(data, start):
    rows = []
    off, prev = start, None
    while off < len(data) - 100:
        got = parse_row(data, off)
        if got is None:
            break
        row, p = got
        if prev is not None and row['_index'] != prev:
            break
        rows.append(row)
        prev = row['_index'] + 1
        # 行间可能垫 1 个 int
        nxt = None
        for pad in (0, 4):
            if p + pad + 8 <= len(data):
                a, b = struct.unpack('<ii', data[p + pad:p + pad + 8])
                if a == prev and 0 <= b < 600:
                    nxt = p + pad
                    break
        if nxt is None:
            # 对象边界: 向前扫描续接（元素表也这样穿插）
            limit = min(p + 65536, len(data) - 100)
            for q in range(p, limit, 4):
                g = parse_row(data, q)
                if g and g[0]['_index'] == prev and g[0]['alias'].isascii() \
                        and g[0]['alias'].isprintable():
                    nxt = q
                    break
        if nxt is None:
            break
        off = nxt
    return rows


def load_lang(outdir):
    p = os.path.join(outdir, 'lang', 'Material.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    return {}


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        data_dir, outdir = args[0], args[1]
    elif len(args) == 1:
        data_dir, outdir = None, args[0]
    else:
        raise SystemExit(__doc__)
    os.makedirs(outdir, exist_ok=True)
    from extract_things import resolve_assets
    path = resolve_assets(data_dir)
    print(f'assets: {path}')
    data = open(path, 'rb').read()
    start = find_table_start(data)
    if start is None:
        raise SystemExit('找不到材质表起点（plain 行）')
    rows = chain_parse(data, start)
    print(f'parsed: {len(rows)} rows')
    if not rows:
        raise SystemExit(1)
    lang = load_lang(outdir)
    cn_by_id = {int(k): v for k, v in lang.items()}
    out = []
    for r in rows:
        L = cn_by_id.get(r['id'], {})
        bits = r['bits'] or []
        tags = r['tag'] or []
        out.append({
            'id': r['id'], 'alias': r['alias'],
            'name_en': r['name'], 'name_jp': r['name_JP'],
            'cn': L.get('name', ''), 'prefix_cn': L.get('altName', ''),
            'category': r['category'], 'tag': tags, 'thing': r['thing'],
            'hardness': r['hardness'], 'tier': r['tier'],
            'weight': r['weight'], 'value': r['value'], 'quality': r['quality'],
            'chance': r['chance'],
            'atk': r['atk'], 'dmg': r['dmg'], 'dv': r['dv'], 'pv': r['pv'],
            'dice': r['dice'], 'bits': bits, 'groups': r['groups'],
            'elements': r['elements'],
            'altName': r['altName'], 'altName_JP': r['altName_JP'],
            'fireproof': 'fire' in bits,
            'acidproof': 'acid' in bits,
            'decay': r['decay'],
        })
    with open(os.path.join(outdir, 'materials.jsonl'), 'w', encoding='utf-8') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    legacy = {r['alias']: {'id': r['id'], 'jp': r['name_jp'], 'en': r['name_en'],
                           'cn': r['cn']} for r in out}
    with open(os.path.join(outdir, 'materials.json'), 'w', encoding='utf-8') as f:
        json.dump(legacy, f, ensure_ascii=False, indent=1)
    print(f"rows: {len(out)}; sample: {out[0]['alias']} cn={out[0]['cn']!r} "
          f"hardness={out[0]['hardness']} bits={out[0]['bits']} value={out[0]['value']}")


if __name__ == '__main__':
    main()
