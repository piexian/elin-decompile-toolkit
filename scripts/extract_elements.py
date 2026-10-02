#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Elin 的 sharedassets0.assets 提取元素表(SourceElement)行数据。

用法: python extract_elements.py [游戏目录或Elin_Data目录] <输出目录>
      不传游戏目录时自动从 Steam 定位（也可用环境变量 ELIN_GAME_DIR 指定）。
产出:
  elements.jsonl  每行一个元素: {id, alias, name_en, name_jp, encSlot, chance,
                  value, encFactor, lvFactor, category, categorySub, tag, detail, ...}

原理: SourceElement.Row 的 Unity 序列化布局（声明序，4 字节对齐）:
  [_index][id][alias][name_JP][name][altname_JP][altname][aliasParent][aliasRef]
  [aliasMtp][parentFactor:f32][lvFactor][encFactor][encSlot][mtp][LV][chance][value]
  [cost:i32[]][geneSlot][sort][target][proc:s[]][type][group][category][categorySub]
  [abilityType:s[]][tag:s[]][thing][eleP][cooldown][charge][radius:f32][max]
  [req:s[]][idTrainer][partySkill][tagTrainer][levelBonus_JP][levelBonus]
  [foodEffect:s[]][langAct:s[]][detail_JP][detail][textPhase_JP][textPhase]
  [textExtra_JP][textExtra][textInc_JP][textInc][textDec_JP][textDec]
  [textAlt_JP:s[]][textAlt:s[]][adjective_JP:s[]][adjective:s[]][pad int=0]
整表从 _void 行(_index=0,id=0)起链式解析，按 [_index 连续递增 + pad=0] 断开；
EA 23.350 共 884 行（group: ELEMENT/SLOT/SKILL/ENC/SPELL/FACTION/...）。
注意: Package/_Elona/Data/Source/SourceElement 是旧类布局的开发遗留文件，不要用。
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from steam_locate import find_game_dir

# SourceElement.Row 序列化字段: (字段名, 类型)  类型: i=int, s=string, f=float,
# ia=int[], sa=string[]
FIELDS = [
    ('_index', 'i'), ('id', 'i'), ('alias', 's'), ('name_JP', 's'), ('name', 's'),
    ('altname_JP', 's'), ('altname', 's'), ('aliasParent', 's'), ('aliasRef', 's'),
    ('aliasMtp', 's'), ('parentFactor', 'f'), ('lvFactor', 'i'), ('encFactor', 'i'),
    ('encSlot', 's'), ('mtp', 'i'), ('LV', 'i'), ('chance', 'i'), ('value', 'i'),
    ('cost', 'ia'), ('geneSlot', 'i'), ('sort', 'i'), ('target', 's'),
    ('proc', 'sa'), ('type', 's'), ('group', 's'), ('category', 's'),
    ('categorySub', 's'), ('abilityType', 'sa'), ('tag', 'sa'), ('thing', 's'),
    ('eleP', 'i'), ('cooldown', 'i'), ('charge', 'i'), ('radius', 'f'), ('max', 'i'),
    ('req', 'sa'), ('idTrainer', 's'), ('partySkill', 'i'), ('tagTrainer', 's'),
    ('levelBonus_JP', 's'), ('levelBonus', 's'), ('foodEffect', 'sa'),
    ('langAct', 'sa'), ('detail_JP', 's'), ('detail', 's'), ('textPhase_JP', 's'),
    ('textPhase', 's'), ('textExtra_JP', 's'), ('textExtra', 's'),
    ('textInc_JP', 's'), ('textInc', 's'), ('textDec_JP', 's'), ('textDec', 's'),
    ('textAlt_JP', 'sa'), ('textAlt', 'sa'), ('adjective_JP', 'sa'),
    ('adjective', 'sa'),
]

OUT_KEYS = ['id', '_index', 'alias', 'name_en', 'name_jp', 'encSlot', 'encFactor',
            'lvFactor', 'mtp', 'LV', 'chance', 'value', 'cost', 'geneSlot', 'sort',
            'target', 'proc', 'type', 'group', 'category', 'categorySub',
            'abilityType', 'tag', 'thing', 'eleP', 'max', 'req', 'idTrainer',
            'detail_jp', 'detail_en']


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


def find_table_start(data):
    """_void 行: [int 0][int 0][len 5]'_void'"""
    i = 0
    while True:
        i = data.find(b'\x05\x00\x00\x00_void', i + 1)
        if i < 0:
            return None
        if struct.unpack('<ii', data[i - 8:i]) == (0, 0):
            return i - 8


def chain_parse(data, start):
    """从表头起按行链式解析，直到 _index 断号或 pad != 0（对象边界）"""
    rows = []
    off, prev = start, -1
    while off < len(data) - 100:
        got = parse_row(data, off)
        if got is None:
            break
        row, p = got
        if p + 4 > len(data):
            break
        pad = struct.unpack('<i', data[p:p + 4])[0]
        if row['_index'] != prev + 1 or pad != 0:
            break
        rows.append(row)
        prev = row['_index']
        off = p + 4
    return rows


def load_lang_names(outdir):
    en, jp = set(), set()
    p = os.path.join(outdir, 'lang', 'Element.json')
    if os.path.exists(p):
        for row in json.load(open(p, encoding='utf-8')).values():
            for k in ('name_EN', 'name'):
                if row.get(k):
                    en.add(row[k])
            if row.get('name_JP'):
                jp.add(row['name_JP'])
    return en, jp


def parse_row(data, off):
    p = off
    row = {}
    for name, typ in FIELDS:
        if typ == 'i':
            if p + 4 > len(data):
                return None
            row[name] = struct.unpack('<i', data[p:p + 4])[0]
            p += 4
        elif typ == 'f':
            if p + 4 > len(data):
                return None
            row[name] = struct.unpack('<f', data[p:p + 4])[0]
            p += 4
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


def load_lang_names(outdir):
    en, jp = set(), set()
    p = os.path.join(outdir, 'lang', 'Element.json')
    if os.path.exists(p):
        for row in json.load(open(p, encoding='utf-8')).values():
            for k in ('name_EN', 'name'):
                if row.get(k):
                    en.add(row[k])
            if row.get('name_JP'):
                jp.add(row['name_JP'])
    return en, jp


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
        raise SystemExit('找不到元素表起点（_void 行）')
    rows = chain_parse(data, start)
    print(f'parsed: {len(rows)} rows (id {rows[0]["id"]}..{rows[-1]["id"]})'
          if rows else '解析 0 行')
    out = []
    for r in rows:
        out.append({
            'id': r['id'], 'alias': r['alias'], 'group': r['group'],
            'name_en': r['name'], 'name_jp': r['name_JP'],
            'encSlot': r['encSlot'], 'encFactor': r['encFactor'],
            'lvFactor': r['lvFactor'], 'mtp': r['mtp'], 'LV': r['LV'],
            'chance': r['chance'], 'value': r['value'], 'cost': r['cost'],
            'geneSlot': r['geneSlot'], 'sort': r['sort'], 'target': r['target'],
            'proc': r['proc'], 'type': r['type'],
            'category': r['category'], 'categorySub': r['categorySub'],
            'abilityType': r['abilityType'], 'tag': r['tag'], 'thing': r['thing'],
            'eleP': r['eleP'], 'max': r['max'], 'req': r['req'],
            'idTrainer': r['idTrainer'], 'detail_jp': r['detail_JP'],
            'detail_en': r['detail'],
        })
    with open(os.path.join(outdir, 'elements.jsonl'), 'w', encoding='utf-8') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    import collections
    print('groups:', dict(collections.Counter(r['group'] for r in rows)))
    enc = [r for r in rows if r['group'] == 'ENC']
    print(f'ENC rows: {len(enc)}')


if __name__ == '__main__':
    main()
