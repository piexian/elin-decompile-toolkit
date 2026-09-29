#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Elin.decompiled.cs 按类拆成单文件(大括号深度追踪, 嵌套类独立成文件, 父类保留其余内容)。
输出: kb/src/classes/<ClassName>.cs; 父类文件中嵌套类位置留占位注释。
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'src', 'Elin.decompiled.cs')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'kb', 'src', 'classes')

DECL = re.compile(r'^(\t*)((?:public|internal|private|protected)\s+)*(?:abstract\s+|static\s+|sealed\s+|partial\s+|readonly\s+|unsafe\s+|new\s+)*(class|enum|interface|struct)\s+([A-Za-z_0-9]+)')

def main():
    lines = open(SRC, encoding='utf-8').read().split('\n')
    n = len(lines)
    # 每行处理完后的花括号深度(去掉注释; 字符串内花括号照常计入, 格式串/插值本身平衡)
    depth = [0] * (n + 1)
    d = 0
    in_block_comment = False
    for i, ln in enumerate(lines):
        s = ln
        if in_block_comment:
            bi = s.find('*/')
            if bi < 0:
                s = ''
            else:
                s = s[bi + 2:]
                in_block_comment = False
        while True:
            bi = s.find('/*')
            if bi < 0:
                break
            bj = s.find('*/', bi)
            if bj < 0:
                s = s[:bi]
                in_block_comment = True
                break
            s = s[:bi] + s[bj + 2:]
        s = s.split('//')[0]
        d += s.count('{') - s.count('}')
        depth[i + 1] = d
    # 找出类型声明: (行号, 声明行所在深度, 名字)
    decls = []
    for i, ln in enumerate(lines):
        m = DECL.match(ln)
        if m and m.group(3) in ('class', 'enum', 'interface', 'struct'):
            decls.append((i, depth[i], m.group(4)))
    # 计算每个类型的结束行: 从声明行后的开大括号起, 到深度回落到声明深度的行为止
    segments = []
    for i, d, name in decls:
        o = i
        while o < n and depth[o + 1] <= d and o - i <= 5:
            o += 1
        if o >= n or o - i > 5 or depth[o + 1] <= d:
            segments.append((i, i + 1, name))  # 单行类型(如一行 enum)
            continue
        j = o + 1
        while j < n and depth[j] > d:
            j += 1
        segments.append((i, j, name))
    # 只保留"没有被其他类型区间包含开头行"的作为顶层? 不: 全部输出, 父类挖掉嵌套段
    # 标记每行属于哪个最内层类型段
    owner = [-1] * n
    for k, (s, e, name) in enumerate(segments):
        for i in range(s, min(e, n)):
            owner[i] = k
    files = {}
    for k, (s, e, name) in enumerate(segments):
        body = []
        i = s
        e = min(e, n)
        while i < e:
            if owner[i] == k:
                body.append(lines[i])
                i += 1
            else:
                nk = owner[i]
                body.append(f'\t\t// [嵌套类型 {segments[nk][2]} -> {segments[nk][2]}.cs]')
                i = max(i + 1, min(segments[nk][1], e))
        files[name] = body
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    used = {}
    for name, body in files.items():
        fn = name
        if fn in used:
            used[fn] += 1
            fn = f'{name}_{used[name]}'
        used[name] = used.get(name, 1)
        with open(os.path.join(OUT, fn + '.cs'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(body).rstrip() + '\n')
    print(f'拆分完成: {len(files)} 个类型 -> {OUT}')

if __name__ == '__main__':
    main()
