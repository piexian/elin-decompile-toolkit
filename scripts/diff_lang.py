#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比两版 lang JSON，列出新增/删除/修改的条目。
用法: python diff_lang.py <旧目录> <新目录>
"""
import json
import os
import sys


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def flat(row):
    """把一行摊平成 {列: 值} 便于比较。"""
    return {k: v for k, v in row.items() if v not in ('', None)}


def main(old_dir, new_dir):
    names = sorted(set(os.listdir(old_dir)) | set(os.listdir(new_dir)))
    total_add = total_del = total_mod = 0
    for name in names:
        if not name.endswith('.json'):
            continue
        op = os.path.join(old_dir, name)
        np_ = os.path.join(new_dir, name)
        if not os.path.exists(op):
            print(f'[新增表] {name}')
            continue
        if not os.path.exists(np_):
            print(f'[删除表] {name}')
            continue
        old, new = load(op), load(np_)
        added = [k for k in new if k not in old]
        removed = [k for k in old if k not in new]
        modified = [k for k in old if k in new and flat(old[k]) != flat(new[k])]
        if not (added or removed or modified):
            continue
        print(f'\n=== {name}  +{len(added)} -{len(removed)} ~{len(modified)} ===')
        for k in added:
            row = new[k]
            label = row.get('name') or row.get('text') or ''
            extra = {c: v for c, v in row.items() if c != 'name' and v not in ('', None)}
            print(f'  [+] {k}  {label}  {json.dumps(extra, ensure_ascii=False)[:220]}')
        for k in removed:
            row = old[k]
            label = row.get('name') or row.get('text') or ''
            print(f'  [-] {k}  {label}')
        for k in modified:
            o, n = flat(old[k]), flat(new[k])
            cols = [c for c in set(o) | set(n) if o.get(c, '') != n.get(c, '')]
            for c in cols:
                ov, nv = str(o.get(c, '')), str(n.get(c, ''))
                if len(ov) > 60:
                    ov = ov[:60] + '…'
                if len(nv) > 60:
                    nv = nv[:60] + '…'
                print(f'  [~] {k}.{c}: {ov}  ->  {nv}')
        total_add += len(added)
        total_del += len(removed)
        total_mod += len(modified)
    print(f'\n合计: +{total_add} -{total_del} ~{total_mod}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
