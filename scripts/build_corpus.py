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
    # 3. 反编译源码按类拷贝
    import shutil
    missing = []
    for src, dst in [('kb/src/classes', 'corpus/code')]:
        s_path = os.path.join(ROOT, src.replace('/', os.sep))
        d_path = os.path.join(D, dst.replace('/', os.sep))
        if not os.path.exists(s_path):
            missing.append(src)
            os.makedirs(d_path, exist_ok=True)   # 留空目录，build_embed_chunks 才不会因为缺路径报错
            continue
        if os.path.exists(d_path):
            shutil.rmtree(d_path)
        shutil.copytree(s_path, d_path)
    print('code copied' + (f'（缺 {", ".join(missing)}，对应语料为空）' if missing else ''))
    # 4. 版本变动语料：直接渲染结构化源表 data/version_changes.json
    # 人工考据知识如需进语料，往 data/knowledge/*.json 加同 schema 的条目，这里一并渲染
    nv = 0
    for src in ['data/version_changes.json'] + sorted(
            os.listdir(os.path.join(ROOT, 'data', 'knowledge'))
            if os.path.isdir(os.path.join(ROOT, 'data', 'knowledge')) else []):
        sp = os.path.join(ROOT, src.replace('/', os.sep))
        if not os.path.isfile(sp):
            continue
        doc = json.load(open(sp, encoding='utf-8'))
        outdir = os.path.join(out, 'versions')
        title = doc.get('topic') or '版本变动'
        if 'versions' in doc:   # version_changes 全量源表 -> 每版本一节 + 总览一节
            b = doc.get('baseline', {})
            overview = ('# 版本变动总览\n\n'
                        f"- 当前基线: {b.get('version', '')}（{b.get('versionInt', '')}，"
                        f"{b.get('channel', '')}，{b.get('buildDate', '')} 构建；"
                        f"语料同步于 {b.get('syncedAt', '')}）\n"
                        + '\n'.join(f"- {v['version']}（{v.get('date', '')}）："
                                    + '；'.join(sec['title'] for sec in v.get('sections', []))
                                    for v in doc.get('versions', [])) + '\n')
            w(outdir, '版本总览', overview)
            nv += 1
            for v in doc.get('versions', []):
                parts = [f"# 版本变动：{v['version']}（{v.get('date', '')}）", '']
                for sec in v.get('sections', []):
                    parts.append(f"## {sec['title']}")
                    parts += [f'- {pt}' for pt in sec.get('points', [])]
                    parts.append('')
                w(outdir, f"版本变动_{v['version']}", '\n'.join(parts) + '\n')
                nv += 1
        else:   # 单主题知识条目 -> 一节
            parts = [f"# {title}", '']
            for sec in doc.get('sections', []):
                parts.append(f"## {sec['title']}")
                parts += [f'- {pt}' for pt in sec.get('points', [])]
                parts.append('')
            w(outdir, title, '\n'.join(parts) + '\n')
            nv += 1
    print(f'versions 语料: {nv} 节（来自 version_changes.json 与 data/knowledge/*.json）')

if __name__ == '__main__':
    main()
