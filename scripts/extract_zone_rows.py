#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 sharedassets0.assets 提取 SourceZone 表（区域/城镇/地城定义行）。
字段顺序按 EA 23.355 反编译 SourceZone.Row 声明序（RowMapping/TypeMapping 截止 detail，
name_L/detail_L/textFlavor_L 是运行时语言扩展列，不在序列化流里）。
用法: python extract_zone_rows.py [游戏目录] <输出目录>
产出: zones_full.json
校验: id 全集必须与 data/lang/Zone.json 键一致（不一致打印差异并退出非 0）。
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


def parse_zone_row(c):
    row = {'_index': c.int()}
    row['id'] = c.string()
    row['parent'] = c.string()
    row['name_JP'] = c.string()
    row['name'] = c.string()
    row['type'] = c.string()
    row['LV'] = c.int()
    row['chance'] = c.int()
    row['faction'] = c.string()
    row['value'] = c.int()
    row['idProfile'] = c.string()
    row['idFile'] = c.str_array(64)
    row['idBiome'] = c.string()
    row['idGen'] = c.string()
    row['idPlaylist'] = c.string()
    row['tag'] = c.str_array(64)
    row['costSkyTravel'] = c.int()
    row['cost'] = c.int()
    row['dev'] = c.int()
    row['image'] = c.string()
    row['pos'] = c.int_array(64)
    row['questTag'] = c.str_array(64)
    row['textFlavor_JP'] = c.string()
    row['textFlavor'] = c.string()
    row['detail_JP'] = c.string()
    row['detail'] = c.string()
    return row


def resolve_assets(data_dir):
    if not data_dir:
        data_dir = find_game_dir()
        if not data_dir:
            raise SystemExit('找不到 Elin 安装目录')
    for cand in (data_dir, os.path.join(data_dir, 'Elin_Data')):
        p = os.path.join(cand, 'sharedassets0.assets')
        if os.path.exists(p):
            return p
    raise SystemExit(f'找不到 sharedassets0.assets（实际得到 {data_dir}）')


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

    tname = 'SourceZone'
    pat = re.compile(re.escape(struct.pack('<i', len(tname))) +
                     re.escape(tname.encode()) + b'\x00')
    ms = list(pat.finditer(data))
    if not ms:
        raise SystemExit(f'{tname}: 找不到对象')
    best, err = None, None
    for m in ms:
        try:
            c = Cursor(data, m.end() + 3)
            c.align()
            c.int()          # SourceData 头部 int
            c.string()       # 编辑器名
            src = c.string()
            if not src.endswith('.xlsx'):
                continue
            count = c.int()
            if not (80 <= count <= 200):
                continue
            rows = []
            while len(rows) < count:
                row = parse_zone_row(c)
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

    lang_path = os.path.join(outdir, 'lang', 'Zone.json')
    lang = json.load(open(lang_path, encoding='utf-8-sig'))
    missing = [r['id'] for r in rows if r['id'] not in lang]
    extra = [k for k in lang if k not in {r['id'] for r in rows}]
    if missing or extra:
        print(f'!! 与语言包不一致: 缺 {missing[:10]} 多 {extra[:10]}')
        sys.exit(1)

    path = os.path.join(outdir, 'zones_full.json')
    json.dump(rows, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  -> {path}')


if __name__ == '__main__':
    main()
