#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""严格按 EA 23.350 反编译字段顺序解析 sharedassets0.assets 里的三张表。
布局已实证校准 (SourceThing 对象头 hex 逐字段核对):
  对象头: m_GameObject PPtr(12) + m_Enabled(1+3pad) + m_Script PPtr(12) + m_Name(str)
          + int 1 + str 编辑器名 + str 'SourceCard.xlsx' + int 行数 + 行数据
  BaseRow: int _index (逐行递增, 用作链式校验)
  RenderRow: tiles[] _tiles[] skins[] colorMod sort value LV chance tempChance snowTile
             name name_JP detail detail_JP _idRenderData _tileType defMat colorType
             category idSound aliasPref components[] factory[] recipeKey[] tag[] W H
             multisize:bool fixedMaterial:bool pref(int[] 26)
  !! colorType 声明存在但不在序列化流里 (与 matColor 同类情况)
  CardRow: id idExtra tierGroup lightData _origin idShadow quality elements[] shadow[]
           size[] light[] loot[] filter[] trait[] idActor[] vals[] name2[] name2_JP[]
  SourceThing.Row: unknown_JP unit_JP naming unit unknown altTiles[] anime[]
           disassemble[] HP weight electricity range attackType offense[] substats[]
           defense[] idToggleExtra idActorEx workTag roomName_JP[] roomName[]
           _altTiles[] ignoreAltFix:bool animeNoSync:bool
  SourceCategory.Row: id uid name_JP name _parent recipeCat slot skill maxStack
           tileDummy installOne:bool ignoreBless tag[] idThing recycle[] costSP
           gift deliver offer ticket sortVal flag
  SourceSpawnList.Row: id parent type category[] idCard[] tag[] filter[]
序列化规则: 字符串 = int32 长度 + UTF-8 + 对齐 4; bool = 1 字节 + 对齐 4;
int[]/str[] = int32 count + 元素; 基类字段在前、声明序即序列化序。
用法: python extract_thing_rows.py [游戏目录] <输出目录>
产出: things_full.jsonl / categories.json / spawnlists.json
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from steam_locate import find_game_dir


class ParseError(Exception):
    pass


class Cursor:
    __slots__ = ('data', 'p')

    def __init__(self, data, p):
        self.data = data
        self.p = p

    def int(self):
        p = self.p
        if p + 4 > len(self.data):
            raise ParseError('eof')
        v = struct.unpack('<i', self.data[p:p + 4])[0]
        self.p = p + 4
        return v

    def align(self):
        self.p = (self.p + 3) & ~3

    def boolean(self):
        v = self.data[self.p]
        self.p += 1
        self.align()
        return bool(v)

    def string(self, maxlen=8192):
        p = self.p
        if p + 4 > len(self.data):
            raise ParseError('eof')
        ln = struct.unpack('<i', self.data[p:p + 4])[0]
        if ln < 0 or ln > maxlen or p + 4 + ln > len(self.data):
            raise ParseError(f'bad str len {ln} @ {p}')
        s = self.data[p + 4:p + 4 + ln].decode('utf-8')
        self.p = (p + 4 + ln + 3) & ~3
        return s

    def int_array(self, limit=100000):
        n = self.int()
        if n < 0 or n > limit:
            raise ParseError(f'bad int[] count {n} @ {self.p - 4}')
        vals = list(struct.unpack(f'<{n}i', self.data[self.p:self.p + 4 * n])) if n else []
        self.p += 4 * n
        return vals

    def str_array(self, limit=64):
        n = self.int()
        if n < 0 or n > limit:
            raise ParseError(f'bad str[] count {n} @ {self.p - 4}')
        return [self.string() for _ in range(n)]


THING_INTS_HEAD = ['colorMod', 'sort', 'value', 'LV', 'chance', 'tempChance', 'snowTile']


def parse_thing_row(c):
    row = {'_index': c.int()}
    row['tiles'] = c.int_array(256)
    row['_tiles'] = c.int_array(256)
    row['skins'] = c.int_array(256)
    for k in THING_INTS_HEAD:
        row[k] = c.int()
    row['name'] = c.string()
    row['name_JP'] = c.string()
    row['detail'] = c.string()
    row['detail_JP'] = c.string()
    row['_idRenderData'] = c.string()
    row['_tileType'] = c.string()
    row['defMat'] = c.string()
    row['colorType'] = c.string()
    row['category'] = c.string()
    row['idSound'] = c.string()
    row['aliasPref'] = c.string()
    row['components'] = c.str_array(64)
    row['factory'] = c.str_array(64)
    row['recipeKey'] = c.str_array(64)
    row['tag'] = c.str_array(64)
    row['W'] = c.int()
    row['H'] = c.int()
    row['multisize'] = c.boolean()
    row['fixedMaterial'] = c.boolean()
    row['pref_ints'] = c.int_array(256)
    row['id'] = c.string()
    row['idExtra'] = c.string()
    row['tierGroup'] = c.string()
    row['lightData'] = c.string()
    row['_origin'] = c.string()
    row['idShadow'] = c.int()
    row['quality'] = c.int()
    row['elements'] = c.int_array(256)
    row['shadow'] = c.int_array(256)
    row['size'] = c.int_array(256)
    row['light'] = c.int_array(256)
    row['loot'] = c.str_array(64)
    row['filter'] = c.str_array(64)
    row['trait'] = c.str_array(64)
    row['idActor'] = c.str_array(64)
    row['vals'] = c.str_array(64)
    row['name2'] = c.str_array(64)
    row['name2_JP'] = c.str_array(64)
    row['unknown_JP'] = c.string()
    row['unit_JP'] = c.string()
    row['naming'] = c.string()
    row['unit'] = c.string()
    row['unknown'] = c.string()
    row['altTiles'] = c.int_array(256)
    row['anime'] = c.int_array(256)
    row['disassemble'] = c.str_array(64)
    row['HP'] = c.int()
    row['weight'] = c.int()
    row['electricity'] = c.int()
    row['range'] = c.int()
    row['attackType'] = c.string()
    row['offense'] = c.int_array(256)
    row['substats'] = c.int_array(256)
    row['defense'] = c.int_array(256)
    row['idToggleExtra'] = c.string()
    row['idActorEx'] = c.string()
    row['workTag'] = c.string()
    row['roomName_JP'] = c.str_array(64)
    row['roomName'] = c.str_array(64)
    row['_altTiles'] = c.int_array(256)
    row['ignoreAltFix'] = c.boolean()
    row['animeNoSync'] = c.boolean()
    return row


def parse_category_row(c):
    row = {'_index': c.int()}
    row['id'] = c.string()
    row['uid'] = c.int()
    row['name_JP'] = c.string()
    row['name'] = c.string()
    row['_parent'] = c.string()
    row['recipeCat'] = c.string()
    row['slot'] = c.int()
    row['skill'] = c.int()
    row['maxStack'] = c.int()
    row['tileDummy'] = c.int()
    row['installOne'] = c.boolean()
    row['ignoreBless'] = c.int()
    row['tag'] = c.str_array(64)
    row['idThing'] = c.string()
    row['recycle'] = c.str_array(64)
    row['costSP'] = c.int()
    row['gift'] = c.int()
    row['deliver'] = c.int()
    row['offer'] = c.int()
    row['ticket'] = c.int()
    row['sortVal'] = c.int()
    row['flag'] = c.int()
    return row


def parse_spawnlist_row(c):
    row = {'_index': c.int()}
    row['id'] = c.string()
    row['parent'] = c.string()
    row['type'] = c.string()
    row['category'] = c.str_array(64)
    row['idCard'] = c.str_array(64)
    row['tag'] = c.str_array(64)
    row['filter'] = c.str_array(64)
    return row


TABLES = {
    'SourceThing': {
        'parse': parse_thing_row,
        'name_len': 11,
        'count_range': (1000, 6000),
        'out': 'things_full.jsonl',
        'jsonl': True,
    },
    'SourceCategory': {
        'parse': parse_category_row,
        'name_len': 14,
        'count_range': (50, 600),
        'out': 'categories.json',
        'jsonl': False,
    },
    'SourceSpawnList': {
        'parse': parse_spawnlist_row,
        'name_len': 15,
        'count_range': (5, 600),
        'out': 'spawnlists.json',
        'jsonl': False,
    },
}


def resolve_assets(data_dir):
    if not data_dir:
        data_dir = find_game_dir()
        if not data_dir:
            raise SystemExit('找不到 Elin 安装目录：请装在 Steam 库里，或用第一个参数指定游戏根目录')
        print(f'自动定位游戏: {data_dir}')
    for cand in (data_dir, os.path.join(data_dir, 'Elin_Data')):
        p = os.path.join(cand, 'sharedassets0.assets')
        if os.path.exists(p):
            return p
    raise SystemExit(f'找不到 sharedassets0.assets（实际得到 {data_dir}）')


def extract_table(data, tname, cfg, outdir, lang_ids=None):
    pat = re.compile(re.escape(struct.pack('<i', cfg['name_len'])) +
                     re.escape(tname.encode()) + b'\x00')
    ms = list(pat.finditer(data))
    if not ms:
        raise SystemExit(f'{tname}: 找不到对象')
    parse, count_lo, count_hi = cfg['parse'], cfg['count_range'][0], cfg['count_range'][1]
    best = None
    for m in ms:
        try:
            c = Cursor(data, m.end() + 3)  # 对齐到名字符串结尾
            c.align()
            c.int()  # SourceData 头部 int
            c.string()  # 编辑器名
            src = c.string()
            if not src.endswith('.xlsx'):
                continue
            count = c.int()
            if not (count_lo <= count <= count_hi):
                continue
            rows = []
            last_err = None
            while len(rows) < count:
                try:
                    row = parse(c)
                except (ParseError, UnicodeDecodeError, struct.error) as e:
                    last = rows[-1] if rows else None
                    print(f'  断链 @ {hex(c.p)} 第 {len(rows)} 行: {e}; 上一行: '
                          f'{last.get("id") if last else None} @ {hex(c.p - 4)}')
                    raise
                if row['_index'] != len(rows):
                    raise ParseError(f'_index 不连续: {row["_index"]} != {len(rows)}')
                rows.append(row)
            best = (rows, m.start(), src)
            break
        except (ParseError, UnicodeDecodeError, struct.error) as e:
            err = e
    if not best:
        raise SystemExit(f'{tname}: 解析失败 ({err})')
    rows, off, src = best
    print(f'{tname}: {len(rows)} 行 @ {hex(off)} (源 {src})')
    # 校验
    if lang_ids is not None:
        bad = [r['id'] for r in rows if r['id'] not in lang_ids]
        if bad:
            print(f'  !! {len(bad)} 个 id 不在语言包: {bad[:8]}')
    path = os.path.join(outdir, cfg['out'])
    with open(path, 'w', encoding='utf-8') as f:
        if cfg['jsonl']:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        else:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f'  -> {path}')
    return rows


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
    print(f'assets: {len(data)} bytes')

    thing_lang = json.load(open(os.path.join(outdir, 'lang', 'Thing.json'), encoding='utf-8'))
    thing_ids = set(thing_lang)
    cat_lang = json.load(open(os.path.join(outdir, 'lang', 'Category.json'), encoding='utf-8'))

    things = extract_table(data, 'SourceThing', TABLES['SourceThing'], outdir, thing_ids)
    cats = extract_table(data, 'SourceCategory', TABLES['SourceCategory'], outdir,
                         set(cat_lang) | {''})
    sls = extract_table(data, 'SourceSpawnList', TABLES['SourceSpawnList'], outdir)

    print('\n--- category 分布(前16) ---')
    from collections import Counter
    cnt = Counter(r['category'] for r in things)
    for k, v in cnt.most_common(16):
        cn = cat_lang.get(k, {}).get('name', '?')
        print(f'  {k or "(空)":16s} {v:5d}  {cn}')
    print('\n--- 关键 spawnlist ---')
    for want in ('shop_junk', 'gacha_junk', 'wreck_junk', 'shop_food', 'all'):
        hit = next((r for r in sls if r['id'] == want), None)
        print(want, '->', json.dumps(hit, ensure_ascii=False) if hit else '缺失!')
    junk = [r for r in things if r['category'] == 'junk']
    print(f'\ncategory=junk 的物品: {len(junk)}')
    for r in junk:
        print(f"  {r['id']:20s} chance={r['chance']:4d} LV={r['LV']:3d} value={r['value']}")


if __name__ == '__main__':
    main()
