#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Elin wiki 开发查询工具。
用法:
  python lookup.py <关键词>          按 id/中文名/英文名/日文名 模糊查所有表
  python lookup.py thing <关键词>    只查物品(含配方数据)
  python lookup.py mat <关键词>      只查材质
  python lookup.py cat <关键词>      只查类别
  python lookup.py ele <id或关键词>  查元素/特性
在工作区根目录(E:\\ElinWiki)下运行。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
LANGDIR = os.path.join(DATA, 'lang')

_cache = {}


def load_lang(name):
    if name not in _cache:
        p = os.path.join(LANGDIR, name + '.json')
        _cache[name] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    return _cache[name]


def show_lang(table_name, rid, row):
    cn = row.get('name', '')
    en = row.get('name_EN', '')
    jp = row.get('name_JP', '')
    print(f'  [{table_name}] id={rid} | CN={cn} | EN={en} | JP={jp}')
    for k in ('detail', 'detail_EN', 'filter', 'version'):
        v = row.get(k)
        if v and not v.isdigit():
            print(f'      {k}: {v[:100]}')


def search_lang(kw):
    kwl = kw.lower()
    hits = 0
    for fn in sorted(os.listdir(LANGDIR)):
        if not fn.endswith('.json'):
            continue
        table = fn[:-5]
        for rid, row in load_lang(table).items():
            fields = [rid, str(row.get('name', '')), str(row.get('name_EN', '')),
                      str(row.get('name_JP', '')), str(row.get('alias', ''))]
            if any(kwl in f.lower() for f in fields):
                show_lang(table, rid, row)
                hits += 1
                if hits > 30:
                    print('  ... (截断, 前30条)')
                    return


def search_things(kw):
    kwl = kw.lower()
    p = os.path.join(DATA, 'things.jsonl')
    if not os.path.exists(p):
        print('  things.jsonl 不存在, 先运行 extract_things.py')
        return
    # 名称 -> 行 映射(语言包), 用于给二进制行附 id/中文名并支持中文检索
    thing_lang = load_lang('Thing')
    id2cn = {rid: row.get('name', '') for rid, row in thing_lang.items()}
    name2id = {}
    for rid, row in thing_lang.items():
        for k in ('name_EN', 'name_JP'):
            v = row.get(k)
            if v and v not in name2id:
                name2id[v] = rid
    hits = 0
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        rid = name2id.get(r.get('name_en', ''), '')
        if not rid:
            rid = next((t for t in reversed(r.get('tail_strings', [])) if t in id2cn), '')
        cn = id2cn.get(rid, '')
        names = [r.get('name_en', ''), r.get('name_jp', ''), rid, cn] + r.get('tail_strings', [])
        if any(kwl in str(n).lower() for n in names):
            print(f"  [thing] {cn or r['name_en']} / {r['name_en']} / {r['name_jp']}  (id={rid or '?'})")
            print(f"      head: {r['head_strings'][:8]}")
            if r.get('components'):
                print(f"      配方: {r['components']} @ {r.get('factory')}")
            if r.get('tail_strings'):
                print(f"      tail: {r['tail_strings'][:8]}")
            hits += 1
            if hits > 20:
                print('  ... (截断, 前20条)')
                return
    if not hits:
        print('  (无物品匹配)')


def search_materials(kw):
    kwl = kw.lower()
    mats = json.load(open(os.path.join(DATA, 'materials.json'), encoding='utf-8'))
    for key, m in mats.items():
        if any(kwl in str(v).lower() for v in [key, m.get('cn', ''), m.get('jp', ''), m.get('en', ''), m.get('id', '')]):
            print(f"  [material] {key} | id={m['id']} | CN={m.get('cn')} | JP={m.get('jp')} | EN={m.get('en')}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == 'thing' and len(args) > 1:
        search_things(args[1])
    elif args[0] == 'mat' and len(args) > 1:
        search_materials(args[1])
    elif args[0] == 'cat' and len(args) > 1:
        kwl = args[1].lower()
        for rid, row in load_lang('Category').items():
            fields = [rid, str(row.get('name', '')), str(row.get('name_EN', '')), str(row.get('name_JP', ''))]
            if any(kwl in f.lower() for f in fields):
                show_lang('Category', rid, row)
    elif args[0] == 'ele' and len(args) > 1:
        kwl = args[1].lower()
        for rid, row in load_lang('Element').items():
            fields = [rid, str(row.get('name', '')), str(row.get('name_EN', '')), str(row.get('name_JP', ''))]
            if any(kwl in f.lower() for f in fields):
                show_lang('Element', rid, row)
    else:
        search_lang(args[0])
        search_things(args[0])
        search_materials(args[0])


if __name__ == '__main__':
    main()
