#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 data/charas_full.jsonl 重生成站内 [[角色表]] 的 603 行数据表。
列结构与站内现有表一致（15 列）：id/名字/别名/默认等级/默认关系/标签/种族/职业/
战斗模式/品级/先天能力/移动AI/默认战时行动及选取概率/默认工作/默认兴趣。
名字等中文取 data/lang/Chara.json（name/aka，`*r` 或空显示「随机」——这些角色
游戏内是随机名）；种族/职业取 Race/Job.json；先天能力=elements 非零对
（元素官方名+等级）；战时行动=actCombat（元素名+权重，缺省 100）；
移动AI=aiParam（目标距离,移动概率）；工作/兴趣经 Hobby.json 的 name_EN 反查中文。
排序按 SourceChara 的 _index（游戏数据序）。
用法: python gen_chara_table.py [输出文件]（缺省 tmp/角色表-重生成.md）
"""
import json
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(*parts):
    with open(os.path.join(WORKSPACE, 'data', *parts), encoding='utf-8-sig') as f:
        return json.load(f)


def main():
    outpath = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORKSPACE, 'tmp', '角色表-重生成.md')
    rows = [json.loads(l) for l in open(os.path.join(WORKSPACE, 'data', 'charas_full.jsonl'), encoding='utf-8-sig')]
    rows.sort(key=lambda r: r.get('_index', 0))
    C = load_json('lang', 'Chara.json')
    R = load_json('lang', 'Race.json')
    J = load_json('lang', 'Job.json')
    E = load_json('lang', 'Element.json')
    H = load_json('lang', 'Hobby.json')

    def norm(s):
        return (s or '').lower().replace('_', '').replace(' ', '')

    alias2cn = {}
    for k, e in E.items():
        for f in ('alias', 'name_EN', 'name_JP'):
            a = e.get(f) or ''
            if a:
                alias2cn.setdefault(norm(a), e.get('name'))
    el_id2cn = {}
    for line in open(os.path.join(WORKSPACE, 'data', 'elements.jsonl'), encoding='utf-8-sig'):
        er = json.loads(line)
        eid = er.get('id')
        cn = (E.get(str(eid), {}) or {}).get('name')
        if cn and cn != '*r':
            el_id2cn[er.get('alias')] = cn
    hobby_cn = {}
    for e in H.values():
        en = e.get('name_EN') or ''
        if en:
            hobby_cn[en] = e.get('name') or en
    # 角色行里存的是简写（Cook/Farm/Rich…），Hobby 表是全称（Cooking/Farming/Extravagance…），
    # 显式映射；Feel 在 Hobby 表无条目，保留原文
    short_map = {
        'Assassination': 'Assassination', 'Bath': 'Bathing', 'Cheer': 'Cheering',
        'Chore': 'Chores', 'Clean': 'Cleaning', 'Cook': 'Cooking', 'Diary': 'Diary',
        'Drug': 'Drug', 'Exercise': 'Exercise', 'Explore': 'Exploration',
        'Farm': 'Farming', 'Fish': 'Fishing', 'Gacha': 'Gacha', 'Game': 'Game',
        'History': 'History', 'Hoard': 'Hoarding', 'Hunt': 'Hunting',
        'Lumberjack': 'Lumberjack', 'Nurse': 'Nursing', 'Paint': 'Painting',
        'Pray': 'Praying', 'Read': 'Reading', 'Research': 'Research',
        'Rich': 'Extravagance', 'Romance': 'Romance', 'Rumor': 'Rumor',
        'Sing': 'Singing', 'Smith': 'Blacksmith', 'Supervising': 'Supervising',
        'TreasureHunt': 'Treasure Hunt',
    }
    raceCN = {k: (v.get('name') or k) for k, v in R.items()}
    jobCN = {k: (v.get('name') or k) for k, v in J.items()}
    for k in list(jobCN):
        if jobCN[k] == '*r':
            jobCN[k] = ''

    def name_of(cid, row):
        e = C.get(cid, {}) or {}
        cn = e.get('name') or ''
        if cn in ('', '*r'):
            return '随机'
        return cn

    def aka_of(cid):
        e = C.get(cid, {}) or {}
        a = e.get('aka') or ''
        return '' if a == '*r' else a

    def fmt_acts(r):
        out = []
        for a in r.get('actCombat') or []:
            parts = a.split('/')
            cn = el_id2cn.get(parts[0]) or alias2cn.get(norm(parts[0])) or parts[0]
            w = parts[1] if len(parts) > 1 else '100'
            out.append(f'{cn}{w}')
        return '、'.join(out)

    def fmt_elements(r):
        els = r.get('elements') or []
        out = []
        for i in range(0, len(els) - 1, 2):
            eid, lv = els[i], els[i + 1]
            if not lv:
                continue
            cn = (E.get(str(eid), {}) or {}).get('name')
            if not cn or cn == '*r':
                cn = str(eid)
            out.append(f'{cn}{lv}')
        return '、'.join(out)

    buf = []
    buf.append('<!-- 本表由 tools/gen_chara_table.py 从 data/charas_full.jsonl（SourceChara 全 603 行，'
               'tools/extract_chara_rows.py 提取自 EA 23.355 的 sharedassets0.assets）重新生成，'
               '名字/别名/种族/职业/能力名均取 data/lang 官方语言包；`*r` 或空名显示「随机」。'
               '来源：data/charas_full.jsonl + data/lang/{Chara,Race,Job,Element,Hobby}.json -->')
    buf.append('来源：data/charas_full.jsonl + data/lang/{Chara,Race,Job,Element,Hobby}.json -->')
    buf.append('')
    buf.append('{| class="wikitable sortable"')
    buf.append('!id\n!名字\n!别名\n!默认等级\n!默认关系\n!标签\n!种族\n!职业\n!战斗模式\n!品级\n!先天能力\n!移动AI\n!默认战时行动及选取概率\n!默认工作\n!默认兴趣')
    for r in rows:
        cid = r['id']
        ai = r.get('aiParam') or []
        ai_txt = f"目标距离{ai[0]},移动概率{ai[1]}" if len(ai) >= 2 else ''
        works = '、'.join(hobby_cn.get(short_map.get(w, w), w) for w in (r.get('works') or []))
        hobbies = '、'.join(hobby_cn.get(short_map.get(h, h), h) for h in (r.get('hobbies') or []))
        buf.append('|-')
        buf.append('\n|\n'.join([
            cid,
            name_of(cid, r),
            aka_of(cid),
            str(r.get('LV', '')),
            r.get('hostility') or '',
            '、'.join(r.get('tag') or []),
            raceCN.get(r.get('race') or '', r.get('race') or ''),
            jobCN.get(r.get('job') or '', r.get('job') or ''),
            r.get('tactics') or '',
            str(r.get('quality', '')),
            fmt_elements(r),
            ai_txt,
            fmt_acts(r),
            works,
            hobbies,
        ]))
    buf.append('|}')
    with open(outpath, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(buf) + '\n')
    print(f'生成 {len(rows)} 行 -> {outpath}')


if __name__ == '__main__':
    main()
