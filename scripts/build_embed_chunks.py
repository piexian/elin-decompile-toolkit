#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 kb/corpus 打包成可直接上传 AstrBot WebUI 的聚合 .md 文件。

AstrBot 对 .md 走 MarkdownChunker(见 astrbot/core/knowledge_base/kb_helper.py)：
  - 每个 markdown 标题独立成一个 chunk；
  - 标题下的正文 <= 分块大小 就是 1 块，超出才递归切；
  - min_chunk_size 默认为 0，**相邻的短块不会合并**。
所以「一个实体一个文件」会让每个实体各占一次嵌入调用（此前 3331 个 data 块平均只有 235 字符）。
本脚本改为：把若干实体打包进同一个标题段落，段落长度顶到目标大小，再把段落拼成大文件。

输出: kb/embed_ready/*.md（按 data / code / doc 分组的聚合文件）+ MANIFEST.md
用法: python tools/build_embed_chunks.py [WebUI 分块大小]
      2048（默认）-> 约 2600 块
      4096        -> 约 1500 块，最快，但检索更粗
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'kb', 'corpus')
OUT = os.path.join(ROOT, 'kb', 'embed_ready')
VERSION = 'EA 23.349'

# WebUI 的「分块大小」。段落必须比它略小，否则段落会被二次切分。
CHUNK_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
SECTION = CHUNK_SIZE - 80  # 80 字符留给标题行和余量
# 单个上传文件的目标字符数，太大 WebUI 一次处理会很慢
BATCH = 240_000

# 渲染 / UI / 音频 / 网络 / 引擎设置类，与 wiki 词条无关，默认不嵌入。
# 想全量嵌入就把它设成空集合。Guild* 不在列（是公会职业数据）。
PRUNE_PREFIX = re.compile(
    r'^(UI|Layer|Render|Mesh|Shader|Sprite|Camera|PostEffect|Refraction|Bloom|'
    r'Audio|Sound|BGM|Net|Steam|Input|Coroutine|Tween|Scene|Effect3D|WebGL|'
    r'Http|Download|Cursor|Scroll|Particle|Weather|Light|Fog|Skybox|Animator|'
    r'Physics|Rigidbody|Collider|Gui)',
    re.I,
)
PRUNE_EXACT = {
    'BaseTileMap', 'TileMapElona', 'CoreDebug', 'ModUtil', 'ModManager',
    'DramaManager', 'DramaCustomSequence', 'Application', 'Point', 'ColorExt',
    'StringExt', 'ListExt', 'MathfExt',
}

DATA_FOLDERS = ['items', 'charas', 'elements', 'materials', 'categories', 'zones']
FOLDER_CN = {
    'items': '物品', 'charas': '角色', 'elements': '元素',
    'materials': '材质', 'categories': '类别', 'zones': '地区',
}


def demote_headings(text):
    """把正文里的 markdown 标题降级为粗体，避免在聚合文件里被再切成独立块。"""
    return re.sub(r'^(#{1,4})\s+(.+)$', r'**\2**', text, flags=re.M)


def split_long(text, limit):
    """把超长文本按 空行 -> 换行 -> 硬切 的顺序切成 <= limit 的段。"""
    if len(text) <= limit:
        return [text]
    parts, cur = [], ''
    for para in re.split(r'\n\s*\n', text):
        cand = (cur + '\n\n' + para) if cur else para
        if cur and len(cand) > limit:
            parts.append(cur)
            cur = para
        else:
            cur = cand
    if cur:
        parts.append(cur)
    final = []
    for p in parts:
        while len(p) > limit:
            cut = p.rfind('\n', 0, limit)
            if cut <= 0:
                cut = limit
            final.append(p[:cut])
            p = p[cut:]
        if p.strip():
            final.append(p)
    return final


def pack(entries, section=SECTION):
    """entries: [(group, title, body)] -> [(title, 合并后的正文)]。
    group 相同的条目尽量排在一起并填进同一段落；跨 group 不混装（保证标题语义干净）。"""
    groups = {}
    for group, title, body in entries:
        groups.setdefault(group, []).append((title, body))
    out = []
    for group, items in groups.items():
        cur, cur_len = [], 0
        for title, body in items:
            need = len(title) + 2 + len(body) + 2
            if cur and cur_len + need > section:
                out.append((make_title(group, cur), '\n\n'.join(b for _, b in cur)))
                cur, cur_len = [], 0
            cur.append((title, body))
            cur_len += need
        if cur:
            out.append((make_title(group, cur), '\n\n'.join(b for _, b in cur)))
    return out


def pack_code(classes, section=SECTION):
    """反编译源码专用：把所有类拉成一条行流，逐行填到接近 section 为止再切段。
    换类时插一行 `// 类: X  来源: ...`，所以跨类拼段也不会丢出处。
    返回 [(段首类名, 围栏包裹的代码正文)]。
    比「先按类切段再合并」好在没有段落边界浪费，每段都顶到上限。"""
    budget = section - 40  # 留给围栏和标题行
    out, buf, size, first, prev = [], [], 0, None, None

    def flush():
        nonlocal buf, size, first
        if buf:
            out.append((first, '```csharp\n' + ''.join(buf).rstrip() + '\n```'))
        buf, size, first = [], 0, None

    for cls, fn, body in classes:
        if prev is not None and cls != prev:
            marker = f'// 类: {cls} (Elin 反编译)  来源: src/classes/{fn}\n'
            if size + len(marker) > budget:
                flush()
            if first is None:
                first = cls
            buf.append(marker)
            size += len(marker)
        for line in body.split('\n'):
            piece = line + '\n'
            if size + len(piece) > budget:
                flush()
            if first is None:
                first = cls
            buf.append(piece)
            size += len(piece)
        prev = cls
    flush()
    return out


def stream_title(names, bodies):
    first = names[0].split('（')[0]
    return first if len(names) == 1 else f'{first} 等 {len(names)} 段（{names[0].split("（")[0]} 起）'


def make_title(group, items):
    """段落标题带上分组名，块脱离上下文时也知道自己在讲哪一类。"""
    first = items[0][0]
    label = f'未归类{group[1:]}' if group.startswith('~') else group
    if len(items) == 1:
        return first
    return f'{label}：{first} 等 {len(items)} 项'


def write_batches(sections, prefix, group):
    """把段落写成若干 <= BATCH 字符的聚合文件，返回 (文件数, 块数, 字符数)。"""
    os.makedirs(OUT, exist_ok=True)
    files, chunks, chars, buf, n = 0, 0, 0, [], 0
    batches = []
    for title, body in sections:
        sec = f'# {title}\n\n{body}'
        if buf and sum(len(x) for x in buf) + len(sec) > BATCH:
            batches.append(buf)
            buf = []
        buf.append(sec)
    if buf:
        batches.append(buf)
    for i, batch in enumerate(batches, 1):
        name = f'{prefix}_{i:02d}.md'
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            f.write(f'<!-- source_type: {group} | version: {VERSION} | '
                    f'part: {i}/{len(batches)} -->\n\n')
            f.write('\n\n'.join(batch).rstrip() + '\n')
        files += 1
        chunks += len(batch)
        chars += sum(len(x) for x in batch)
    return files, chunks, chars


def load_category_ids():
    """类别 id 集合（Category.json 的行 id，如 wood / food / obj / _furniture）。"""
    p = os.path.join(ROOT, 'data', 'lang', 'Category.json')
    try:
        rows = json.load(open(p, encoding='utf-8'))
    except OSError:
        return set()
    ids = {r.get('name_EN', '') for r in rows.values()}
    ids |= set(rows.keys())
    return {i for i in ids if i}


def item_category(text, cat_ids):
    """从 items 条目的「其他字段」token 列表里认出类别。
    token 可能是类别本身（wood），也可能是它的细分（obj_S / meal_cookie）。"""
    m = re.search(r'^- 其他字段: (.+)$', text, re.M)
    if not m:
        return None
    for tok in (t.strip() for t in m.group(1).split('/')):
        if tok in cat_ids:
            return tok
        for cid in cat_ids:
            if tok.startswith(cid + '_'):
                return cid
    return None


def parse_entry(text):
    """拆出 (标题, 正文)；标题是第一条一级标题。"""
    text = text.strip()
    m = re.match(r'^#\s+(.+?)\n(.*)$', text, re.S)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return text.split('\n', 1)[0][:60], text


def num_key(s):
    m = re.search(r'(\d+)', s)
    return (0, int(m.group(1))) if m else (1, 0)


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)
    cat_ids = load_category_ids()
    report = []

    # ---- data：实体条目 ----
    entries = []
    for folder in DATA_FOLDERS:
        d = os.path.join(SRC, folder)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith('.md'):
                continue
            text = open(os.path.join(d, fn), encoding='utf-8').read()
            title, body = parse_entry(text)
            body = demote_headings(body)
            # 打包后段落标题只保留第一个实体，所以每个实体都要在正文里自带
            # 一行自己的名字 + id，否则同段落里后面的实体的 id 和主名就丢了。
            body = f'**{title}**\n{body}'
            if folder == 'items':
                group = item_category(text, cat_ids) or f'~{FOLDER_CN[folder]}'
            else:
                group = FOLDER_CN[folder]
            entries.append((group, title, body))
    entries.sort(key=lambda e: (e[0], num_key(e[1])))
    sections = pack(entries)
    report.append(('data',) + write_batches(sections, 'data', 'data'))

    # ---- doc：notes / drafts ----
    entries = []
    for folder in ['notes', 'drafts']:
        base = os.path.join(SRC, folder)
        for root, _, files in os.walk(base):
            for fn in sorted(files):
                if not fn.endswith(('.md', '.txt')):
                    continue
                path = os.path.join(root, fn)
                rel = os.path.relpath(path, SRC).replace('\\', '/')
                text = open(path, encoding='utf-8').read()
                name = rel.rsplit('.', 1)[0]
                # 先按二级标题切，再降级标题，保证每个段落只有一个 markdown 标题
                for i, sec in enumerate(re.split(r'\n(?=##\s)', text), 1):
                    sec = sec.strip()
                    if not sec:
                        continue
                    sec = re.sub(r'^##\s+(.+)$', r'# \1', sec, flags=re.M)
                    sec = demote_headings(sec)
                    # 没有二级标题的整篇草稿会变成一个超长段落，必须按长度再切
                    parts = split_long(sec, SECTION)
                    for j, part in enumerate(parts, 1):
                        tag = f' 第{i}节' + (f'/{len(parts)}段' if len(parts) > 1 else '')
                        entries.append((name, f'{name}（{rel}{tag}）', part))
    entries.sort(key=lambda e: e[0])
    sections = pack(entries)
    report.append(('doc',) + write_batches(sections, 'doc', 'doc'))

    # ---- code：反编译类 ----
    # 按行流式切割而不是先按类切段——段落贪心切会留 20~40% 空隙，
    # 直接按行填满 SECTION，每段都能顶到上限，块数最接近 总字符/分块大小。
    classes = []
    codedir = os.path.join(SRC, 'code')
    skipped_empty = 0
    skipped_pruned = 0
    for fn in sorted(os.listdir(codedir)):
        if not fn.endswith('.cs'):
            continue
        cls = fn[:-3]
        if PRUNE_PREFIX.match(cls) or cls in PRUNE_EXACT:
            skipped_pruned += 1
            continue
        text = open(os.path.join(codedir, fn), encoding='utf-8').read()
        body = text.strip()
        # 空壳类（只有 class/接口声明和一对花括号）对检索没有价值
        if len(re.sub(r'[\s{}/\[\]():;,]*class[\w\s]*$', '', body, flags=re.M)) < 40:
            skipped_empty += 1
            continue
        classes.append((cls, fn, body))
    sections = pack_code(classes)
    report.append(('code',) + write_batches(sections, 'code', 'code'))

    # ---- 清单 ----
    total_c = sum(r[2] for r in report)
    total_f = sum(r[1] for r in report)
    lines = [
        '# AstrBot 上传清单',
        '',
        f'游戏版本 **{VERSION}**。每个 `# 标题` 段落 = WebUI 的一个文本块，'
        f'整目录 **{total_f} 个文件 / 约 {total_c} 块**，可以一次全量重建。',
        '',
        '| 文件前缀 | 上传文件数 | 段落数（≈嵌入块数） | 字符数 |',
        '|---|---|---|---|',
    ]
    for group, f_, c_, ch_ in report:
        lines.append(f'| `{group}_*.md` | {f_} | {c_} | {ch_:,} |')
    lines += [
        f'| **合计** | **{total_f}** | **{total_c}** | |',
        '',
        '## WebUI 设置',
        '',
        f'- **分块大小设 {CHUNK_SIZE}、分块重叠 100**。本目录的段落都按 {SECTION} 字符打包，'
        '一个段落正好一个块，不会被二次切分。**切分参数和本目录是配套的**：改了分块大小就要重跑 '
        f'`python tools/build_embed_chunks.py <新的分块大小>`。',
        f'- 想更快：重跑 `python tools/build_embed_chunks.py 4096`，块数约 {total_c // 2}，'
        '但单块更大、检索更粗。mistral-embed 支持 8192 token，4096 字符不会超。',
        f'- 块变大后**检索数量要跟着降**：块是 {CHUNK_SIZE} 字符时，'
        f'稠密检索 / 稀疏检索建议设 **15 / 15**（设 50 会一次塞进 '
        f'{50 * CHUNK_SIZE // 1000}K 字符，上下文又慢又稀释）。',
        '',
        '## 剔除内容',
        '',
        f'- 渲染 / UI / 音频 / 网络 / 引擎设置类 **{skipped_pruned} 个**（见 `tools/build_embed_chunks.py` '
        '的 `PRUNE_PREFIX` / `PRUNE_EXACT`，设成空即可全量嵌入）。',
        f'- 空壳类（只有类声明没有实现）**{skipped_empty} 个**。',
    ]
    with open(os.path.join(OUT, 'MANIFEST.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    for group, f_, c_, ch_ in report:
        print(f'{group}: {f_} 个聚合文件 -> {c_} 块, {ch_:,} 字符')
    print(f'合计 {total_c} 块 / {total_f} 个文件；剔除空壳类 {skipped_empty}、无关类 {skipped_pruned}')
    print('WebUI 分块大小请设', CHUNK_SIZE)
    print('输出:', OUT)


if __name__ == '__main__':
    main()
