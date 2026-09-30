#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把工作区数据转成嵌入(RAG)友好的文档语料: 每个实体一个 .md 小节。
输出: kb/corpus/{items,charas,elements,materials,categories,zones}/<id>.md
运行: 在 E:\\ElinWiki 下 python tools/build_corpus.py
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'kb')
lang = lambda n: json.load(open(os.path.join(ROOT, 'data', 'lang', n + '.json'), encoding='utf-8'))

def w(outdir, name, text):
    os.makedirs(outdir, exist_ok=True)
    name = re.sub(r'[\s]+', ' ', name)
    name = re.sub(r'[\\/:*?"<>|]', '_', name)[:80]
    with open(os.path.join(outdir, name + '.md'), 'w', encoding='utf-8') as f:
        f.write(text)

PLACEHOLDER = {'*r', '*', '-', '?', '　'}

# 语料侧的待办/编辑状态过滤。只动 kb/ 里的拷贝，工作区的 drafts/notes 保持原样。
TODO_SENT = re.compile(r'(?:待补充|有待补充|待考证|待补全|待完善|待更新|待重写)\s*[。.]?\s*$')
TODO_WORD = re.compile(r'待补充|有待补充|待考证|待补全|待完善|待更新|待重写|待创建')
STATUS_CELL = re.compile(r'\|\|\s*(?:待创建|已有|✅[^|]*|📝[^|]*|❌[^|]*)\s*$')
SECTION_TODO = re.compile(r'^(=+)\s*待补充[^=]*\1\s*$')


def sanitize_kb_doc(text):
    """剔除 wiki 编辑状态：表格状态列、纯待办句、句尾待办从句、待补充章节。"""
    out, dropped, lines = [], 0, text.split('\n')
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = SECTION_TODO.match(ln.strip())
        if m:
            # 待补充章节：标题连同其正文一并丢弃（到下一个同级或更高级标题）
            level = len(m.group(1))
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt.startswith('=') and len(nxt) - len(nxt.lstrip('=')) <= level:
                    break
                i += 1
            dropped += 1
            continue
        stripped_cell = STATUS_CELL.sub('', ln)
        if stripped_cell != ln:
            dropped += 1
            ln = stripped_cell
        kw = TODO_WORD.search(ln)
        if kw:
            head = ln[:kw.start()]
            # 待办从句前的最后一个分句分隔符；没有分隔符说明待办就是整句谓语 → 整行丢弃
            pos = max(head.rfind('，'), head.rfind(','), head.rfind('：'),
                      head.rfind(':'), head.rfind('、'))
            prefix = head[:pos].rstrip() if pos > 0 else ''
            body = prefix.removeprefix('* ').removeprefix('- ').strip()
            if pos > 0 and len(body) >= 8 and not body.endswith(('的', '与', '和', '及', '等', '是')):
                out.append(prefix.rstrip() + ('。' if not prefix.rstrip().endswith(('。', '.')) else ''))
            else:
                dropped += 1
            i += 1
            continue
        out.append(ln)
        i += 1
    return '\n'.join(out), dropped


def is_placeholder(v):
    return (v or '').strip() in PLACEHOLDER


def build_lang_corpus(table, outdir, base_fields=('name', 'detail', 'aka')):
    """生成语言表语料。

    官方 CN 语言包对未翻译的行会在 name 列填 `*r` 占位符，真正的日文/英文名
    落在 name_EN / detail_JP 等列（有时是整行列错位）。只导出中文列会把这些
    条目的名字全丢掉——Chara 表有 139/598 行属于这种情况。所以这里把所有
    *_EN / *_JP 列都带出来，占位符本身换成可检索的说明。
    """
    n = 0
    for rid, row in lang(table).items():
        cn = row.get('name', '')
        alts = [row.get(k) for k in ('name_JP', 'name_EN', 'detail_JP', 'detail_EN')
                if row.get(k) and not is_placeholder(row.get(k))]
        if is_placeholder(cn):
            # 未翻译：标题用日文/英文原名顶上，别让整条只剩一个占位符
            head = alts[0] if alts else '（待官方翻译）'
        else:
            head = cn or alts[0] if alts else rid
        parts = [f"# {head}（{table} id={rid}）", '']
        for f in base_fields:
            v = row.get(f)
            if v and not is_placeholder(v):
                parts.append(f'- {f}: {v}')
        if is_placeholder(cn):
            parts.append('- 中文名: 官方未翻译（语言包占位符 *r）')
        # 其余 *_EN / *_JP 列（含 detail_JP 这类描述的译名）
        for k in sorted(row):
            if not (k.endswith('_EN') or k.endswith('_JP')) or k in base_fields:
                continue
            v = row[k]
            if v and not is_placeholder(v):
                parts.append(f'- {k}: {v}')
        w(outdir, f'{rid}_{head}', '\n'.join(parts) + '\n')
        n += 1
    return n

def main():
    out = os.path.join(D, 'corpus')
    # 先清空——实体文件名里带译名，改了字段或译名后旧文件会留下来变成重复条目
    import shutil
    if os.path.exists(out):
        shutil.rmtree(out)
    # 1. 语言表语料
    print('Chara:', build_lang_corpus('Chara', os.path.join(out, 'charas')))
    print('Element:', build_lang_corpus('Element', os.path.join(out, 'elements')))
    print('Material:', build_lang_corpus('Material', os.path.join(out, 'materials')))
    print('Category:', build_lang_corpus('Category', os.path.join(out, 'categories')))
    print('Zone:', build_lang_corpus('Zone', os.path.join(out, 'zones')))
    # 2. 物品: things.jsonl + Thing.json 联结
    thing = lang('Thing')
    id2row = thing
    name2id = {}
    for rid, row in thing.items():
        for k in ('name_EN', 'name_JP'):
            v = row.get(k)
            if v and v not in name2id:
                name2id[v] = rid
    n = 0
    for line in open(os.path.join(ROOT, 'data', 'things.jsonl'), encoding='utf-8'):
        r = json.loads(line)
        rid = name2id.get(r['name_en'], '') or next((t for t in r.get('tail_strings', []) if t in id2row), '')
        lrow = id2row.get(rid, {})
        cn = lrow.get('name', '')
        parts = [f"# {cn or r['name_en']}（物品 id={rid or '?'}）", '']
        parts.append(f"- 英文名: {r['name_en']} / 日文名: {r['name_jp']}")
        if cn: parts.append(f"- 中文名: {cn}")
        head = r.get('head_strings', [])
        if len(head) >= 6:
            parts.append(f"- 材质: {head[4] if len(head)>4 else ''} / 组: {head[5] if len(head)>5 else ''}")
        if r.get('components') and r['components'] != ['-']:
            parts.append(f"- 配方: {' + '.join(r['components'])} @ {'/'.join(r.get('factory') or [])}")
        if lrow.get('detail'):
            parts.append(f"- 描述: {lrow['detail']}")
        tail = [t for t in r.get('tail_strings', []) if t and not t.startswith('#')]
        if tail:
            parts.append(f"- 其他字段: {' / '.join(tail[:8])}")
        w(os.path.join(out, 'items'), f"{rid or r['name_en']}", '\n'.join(parts) + '\n')
        n += 1
    print('items:', n)
    # 3. 代码/笔记/草稿直接进语料(按类/按文件)
    # notes 与 drafts 是 wiki 工作文档，带「待补充/待创建」之类的编辑状态；
    # 嵌入语料里这些是噪音，拷贝时过一遍 sanitize_kb_doc，工作区原文件不动。
    import shutil
    SKIP_NOTES = {'对标清单.md'}   # 站内缺口状态跟踪表，纯编辑状态，不进知识库
    missing = []
    stripped = 0
    for src, dst, do_sanitize in [('kb/src/classes', 'corpus/code', False),
                                  ('kb/notes', 'corpus/notes', True),
                                  ('kb/drafts', 'corpus/drafts', True)]:
        s = os.path.join(ROOT, src.replace('/', os.sep))
        d = os.path.join(D, dst.replace('/', os.sep))
        if not os.path.exists(s):
            missing.append(src)
            os.makedirs(d, exist_ok=True)   # 留空目录，build_embed_chunks 才不会因为缺路径报错
            continue
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        for root, dirs, names in os.walk(s):
            dirs[:] = [x for x in dirs if x != '__pycache__']
            for fn in names:
                sp = os.path.join(root, fn)
                dp = os.path.join(d, os.path.relpath(sp, s))
                os.makedirs(os.path.dirname(dp), exist_ok=True)
                if do_sanitize and fn.endswith(('.md', '.txt')):
                    if fn in SKIP_NOTES:
                        stripped += 1
                        continue
                    text = open(sp, encoding='utf-8').read()
                    clean, n = sanitize_kb_doc(text)
                    stripped += n
                    open(dp, 'w', encoding='utf-8', newline='\n').write(clean)
                else:
                    shutil.copy2(sp, dp)
    print('code/notes/drafts copied' + (f'（缺 {", ".join(missing)}，对应语料为空）' if missing else '')
          + (f'；语料侧剔除待办/状态 {stripped} 处' if stripped else ''))

if __name__ == '__main__':
    main()
