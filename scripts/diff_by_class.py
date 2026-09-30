#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把单文件反编译的 unified diff 归属到外层类型，输出每个类型的改动量与片段。
用法: python diff_by_class.py <旧cs> <新cs> <diff文件>
"""
import bisect
import re
import sys
from collections import defaultdict

# 外层类型声明行（缩进 0 的 public/internal/abstract/... class|struct|interface|enum）
TYPE_RE = re.compile(
    r'^(?:\[[^\]]*\]\s*)?'
    r'(?:public|internal|private|protected|abstract|sealed|static|partial|unsafe|readonly|ref)'
    r'[\w\s<>,\.\[\]]*?\b(class|struct|interface|enum|record)\s+([A-Za-z_]\w*)'
)
HUNK_UNIFIED = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)')
HUNK_NORMAL = re.compile(r'^(\d+)(?:,(\d+))?[acd]')


def hunk_start(line, cur_new):
    """返回该行是否为 hunk 头及新文件起始行。兼容 unified(@@)与 normal(3,5c) 两种 diff。"""
    m = HUNK_UNIFIED.match(line)
    if m:
        return True, int(m.group(1))
    m = HUNK_NORMAL.match(line)
    if m:
        return True, int(m.group(2) or m.group(1))
    return False, cur_new


def scan_types(path):
    """返回 [(行号, 类型全名)]，行号为 1-based。"""
    out = []
    ns = None
    with open(path, encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f, 1):
            if line.startswith('namespace '):
                ns = line.strip().rstrip('{').strip()[len('namespace '):].strip()
            elif line.startswith('}'):
                ns = None
            m = TYPE_RE.match(line)
            if m:
                kind, name = m.group(1), m.group(2)
                full = f'{ns}.{name}' if ns else name
                out.append((i, full, kind))
    return out


def main(old_path, new_path, diff_path):
    types = scan_types(new_path)
    lines = [t[0] for t in types]
    stats = defaultdict(lambda: {'+': 0, '-': 0, 'hunks': 0})
    samples = defaultdict(list)
    cur_old = cur_new = 0
    with open(diff_path, encoding='utf-8', errors='ignore') as f:
        for line in f:
            is_hunk, start = hunk_start(line, cur_new)
            if is_hunk:
                cur_new = start
                idx = bisect.bisect_right(lines, cur_new) - 1
                key = types[idx][1] if idx >= 0 else '<file scope>'
                stats[key]['hunks'] += 1
                continue
            if line.startswith('+++') or line.startswith('---'):
                continue
            if line[:1] in '<>+-' and not line.startswith(('<<<', '>>>', '===')):
                idx = bisect.bisect_right(lines, cur_new) - 1
                key = types[idx][1] if idx >= 0 else '<file scope>'
                if line[0] in '>+':
                    stats[key]['+'] += 1
                else:
                    stats[key]['-'] += 1
                if len(samples[key]) < 14:
                    samples[key].append(line.rstrip())

    ranked = sorted(stats.items(), key=lambda kv: -(kv[1]['+'] + kv[1]['-']))
    print(f'共 {len(ranked)} 个类型有改动\n')
    for name, s in ranked:
        print(f'--- {name}   +{s["+"]} -{s["-"]}  ({s["hunks"]} 处)')
        for ln in samples[name]:
            print('   ' + ln[:200])
        if s['+'] + s['-'] > 14:
            print('   ...')
        print()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
