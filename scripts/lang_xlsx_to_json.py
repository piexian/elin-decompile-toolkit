#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Elin 官方语言包 xlsx 转成 JSON。
用法: python lang_xlsx_to_json.py [xlsx路径或目录] <输出目录>
      第一个参数缺省时自动定位游戏里的官方简中语言包（也可用 ELIN_GAME_DIR 指定游戏目录）。
输出: <输出目录>/<文件名>.json  { "行id": {列名: 值, ...}, ... }
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_shared_strings(z):
    """共享字符串表必须按 <si> 聚合——OOXML 的 <v> 索引对应 <si> 而非 <t>，
    富文本 <si> 含多个 <r><t> 段，按 <t> 抓会让首个富文本之后的所有索引错位
    （EA23.351 的 Thing.xlsx: 9319 个 si vs 9640 个 t，21 张表受影响）。
    ET 同时完成 XML 实体解码。"""
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    out = []
    for si in root.findall('m:si', ns):
        out.append(''.join(t.text or '' for t in si.iter('{%s}t' % ns['m'])))
    return out


def load_xlsx(path):
    z = zipfile.ZipFile(path)
    strs = load_shared_strings(z)
    sheet = z.read('xl/worksheets/sheet1.xml').decode('utf-8', 'ignore')
    rows = []
    for r in re.findall(r'<row[^>]*>(.*?)</row>', sheet, re.S):
        vals = []
        pos = 0
        for m in re.finditer(r'<c\b([^>]*?)(?:/>|>(.*?)</c>)', r, re.S):
            attrs, inner = m.group(1), m.group(2)
            # 23.351 起导出的 xlsx 省略空单元格，必须按 r="C3" 的列坐标回填，
            # 否则空格后的所有列左移错位；无 r 属性的旧文件退回顺序填充
            cm = re.search(r'\br="([A-Z]+)\d+"', attrs)
            if cm:
                idx = 0
                for ch in cm.group(1):
                    idx = idx * 26 + ord(ch) - 64
                idx -= 1
            else:
                idx = pos
            while len(vals) <= idx:
                vals.append('')
            vm = re.search(r'<v>(.*?)</v>', inner or '')
            if vm:
                v = vm.group(1)
                vals[idx] = strs[int(v)] if 't="s"' in attrs else v
            pos = idx + 1
        rows.append(vals)
    return rows


def convert(path, outdir):
    rows = load_xlsx(path)
    if not rows:
        return 0
    hdr = rows[0]
    table = {}
    for vals in rows[1:]:
        if not vals or not vals[0]:
            continue
        table[vals[0]] = {h: v for h, v in zip(hdr, vals)}
    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, name + '.json'), 'w', encoding='utf-8') as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
    return len(table)


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        src, outdir = args[0], args[1]
    elif len(args) == 1:
        # 只给输出目录 -> 自动定位官方简中语言包
        outdir = args[0]
        from steam_locate import find_game_dir, lang_cn_dir
        g = find_game_dir()
        if not g:
            raise SystemExit('找不到 Elin 安装目录：请传语言包路径，或用环境变量 ELIN_GAME_DIR 指定游戏目录')
        src = lang_cn_dir(g)
        print(f'自动定位语言包: {src}')
    else:
        raise SystemExit(__doc__)
    files = []
    if os.path.isdir(src):
        for root, _, names in os.walk(src):
            files += [os.path.join(root, n) for n in names if n.endswith('.xlsx')]
    else:
        files = [src]
    for f in sorted(files):
        try:
            n = convert(f, outdir)
            print(f'{os.path.basename(f)}: {n} rows')
        except Exception as e:
            print(f'{os.path.basename(f)}: FAILED {e}')


if __name__ == '__main__':
    main()
