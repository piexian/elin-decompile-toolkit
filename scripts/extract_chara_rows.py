#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""严格解析 sharedassets0.assets 里的 SourceChara / SourceRace / SourceJob。
布局与 extract_thing_rows.py 同一套机制（基类字段在前、声明序=序列化序）：
  SourceChara.Row : CardRow → RenderRow 前缀 + CardRow 字段 + 角色专属尾部
  SourceRace.Row / SourceJob.Row : BaseRow + 各自字段
用法: python extract_chara_rows.py [游戏目录] <输出目录>
产出: charas_full.jsonl / races.json / jobs.json
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_thing_rows import Cursor, resolve_assets


def parse_chara_row(c):
    row = {'_index': c.int()}
    row['tiles'] = c.int_array(256)
    row['_tiles'] = c.int_array(256)
    row['skins'] = c.int_array(256)
    for k in ('colorMod', 'sort', 'value', 'LV', 'chance', 'tempChance', 'snowTile'):
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
    row['pref_ints'] = c.int_array(64)
    row['id'] = c.string()
    row['idExtra'] = c.string()
    row['tierGroup'] = c.string()
    row['lightData'] = c.string()
    row['_origin'] = c.string()
    row['idShadow'] = c.int()
    row['quality'] = c.int()
    row['elements'] = c.int_array(256)
    row['shadow'] = c.int_array(64)
    row['size'] = c.int_array(64)
    row['light'] = c.int_array(64)
    row['loot'] = c.str_array(64)
    row['filter'] = c.str_array(64)
    row['trait'] = c.str_array(64)
    row['idActor'] = c.str_array(64)
    row['vals'] = c.str_array(64)
    row['name2'] = c.str_array(64)
    row['name2_JP'] = c.str_array(64)
    row['_id'] = c.int()
    row['aka_JP'] = c.string()
    row['aka'] = c.string()
    row['tiles_snow'] = c.int_array(256)
    row['hostility'] = c.string()
    row['biome'] = c.string()
    row['race'] = c.string()
    row['job'] = c.string()
    row['tactics'] = c.string()
    row['aiIdle'] = c.string()
    row['aiParam'] = c.int_array(64)
    row['actCombat'] = c.str_array(64)
    row['mainElement'] = c.str_array(64)
    row['equip'] = c.string()
    row['gachaFilter'] = c.str_array(64)
    row['tone'] = c.string()
    row['actIdle'] = c.str_array(64)
    row['bio'] = c.string()
    row['faith'] = c.string()
    row['works'] = c.str_array(64)
    row['hobbies'] = c.str_array(64)
    row['idText'] = c.string()
    row['moveAnime'] = c.string()
    row['recruitItems'] = c.str_array(64)
    row['staticSkin'] = c.boolean()
    row['_tiles_snow'] = c.int_array(256)
    row['skinAntiSpider'] = c.int()
    return row


def parse_race_row(c):
    row = {'_index': c.int()}
    row['id'] = c.string()
    row['name_JP'] = c.string()
    row['name'] = c.string()
    row['playable'] = c.int()
    row['tag'] = c.str_array(64)
    for k in ('life', 'mana', 'vigor', 'DV', 'PV', 'PDR', 'EDR', 'EP',
              'STR', 'END', 'DEX', 'PER', 'LER', 'WIL', 'MAG', 'CHA',
              'SPD', 'INT', 'martial', 'pen'):
        row[k] = c.int()
    row['elements'] = c.int_array(256)
    row['skill'] = c.string()
    row['figure'] = c.string()
    row['geneCap'] = c.int()
    row['material'] = c.string()
    row['corpse'] = c.str_array(64)
    row['loot'] = c.str_array(64)
    row['blood'] = c.int()
    row['meleeStyle'] = c.string()
    row['castStyle'] = c.string()
    row['EQ'] = c.str_array(64)
    row['sex'] = c.int()
    row['age'] = c.int_array(64)
    row['height'] = c.int()
    row['breeder'] = c.int()
    row['food'] = c.str_array(64)
    row['fur'] = c.string()
    row['detail_JP'] = c.string()
    row['detail'] = c.string()
    return row


def parse_job_row(c):
    row = {'_index': c.int()}
    row['id'] = c.string()
    row['name_JP'] = c.string()
    row['name'] = c.string()
    row['playable'] = c.int()
    for k in ('STR', 'END', 'DEX', 'PER', 'LER', 'WIL', 'MAG', 'CHA', 'SPD'):
        row[k] = c.int()
    row['elements'] = c.int_array(256)
    row['weapon'] = c.str_array(64)
    row['equip'] = c.string()
    row['domain'] = c.int_array(256)
    row['detail_JP'] = c.string()
    row['detail'] = c.string()
    return row


TABLES = {
    'SourceChara': {'parse': parse_chara_row, 'name_len': 11,
                    'count_range': (100, 5000), 'out': 'charas_full.jsonl', 'jsonl': True},
    'SourceRace': {'parse': parse_race_row, 'name_len': 10,
                   'count_range': (20, 600), 'out': 'races.json', 'jsonl': False},
    'SourceJob': {'parse': parse_job_row, 'name_len': 9,
                  'count_range': (10, 300), 'out': 'jobs.json', 'jsonl': False},
}


def extract_table(data, tname, cfg, outdir, valid_ids=None):
    pat = re.compile(re.escape(struct.pack('<i', cfg['name_len'])) +
                     re.escape(tname.encode()) + b'\x00')
    ms = list(pat.finditer(data))
    if not ms:
        raise SystemExit(f'{tname}: 找不到对象')
    parse = cfg['parse']
    best, err = None, None
    for m in ms:
        try:
            c = Cursor(data, m.end() + 3)
            c.align()
            c.int()
            c.string()
            src = c.string()
            if not src.endswith('.xlsx'):
                continue
            count = c.int()
            if not (cfg['count_range'][0] <= count <= cfg['count_range'][1]):
                continue
            rows = []
            while len(rows) < count:
                row = parse(c)
                if row['_index'] != len(rows):
                    raise ParseError(f'_index {row["_index"]} != {len(rows)}')
                rows.append(row)
            best = (rows, src)
            break
        except Exception as e:
            err = e
    if not best:
        raise SystemExit(f'{tname}: 解析失败 ({err})')
    rows, src = best
    bad = [r['id'] for r in rows if valid_ids and r['id'] not in valid_ids]
    print(f'{tname}: {len(rows)} 行 (源 {src})' + (f'  !! {len(bad)} 个 id 不在语言包: {bad[:5]}' if bad else ''))
    path = os.path.join(outdir, cfg['out'])
    with open(path, 'w', encoding='utf-8') as f:
        if cfg['jsonl']:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        else:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    return rows


class ParseError(Exception):
    pass


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        data_dir, outdir = args[0], args[1]
    else:
        data_dir, outdir = None, args[0] if args else 'data'
    os.makedirs(outdir, exist_ok=True)
    data = open(resolve_assets(data_dir), 'rb').read()
    lang = lambda n: set(json.load(open(os.path.join(outdir, 'lang', n + '.json'), encoding='utf-8')))
    chara_ids, race_ids, job_ids = lang('Chara'), lang('Race'), lang('Job')
    extract_table(data, 'SourceChara', TABLES['SourceChara'], outdir, chara_ids)
    extract_table(data, 'SourceRace', TABLES['SourceRace'], outdir, race_ids)
    extract_table(data, 'SourceJob', TABLES['SourceJob'], outdir, job_ids)


if __name__ == '__main__':
    main()
