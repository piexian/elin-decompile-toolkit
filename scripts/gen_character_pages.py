#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按"阿什兰德页"规格生成角色页草稿。
数据源: SourceChara(二进制) + Chara.json(name/aka/detail) + Race/Job.json + Drama xlsx(CN台词)。
用法: python gen_character_pages.py [游戏目录]
      游戏目录也可用环境变量 ELIN_GAME_DIR 指定；缺省取 Steam 默认路径。
"""
import json, os, re, struct, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _game_dir():
    if len(sys.argv) > 1:
        return sys.argv[1]
    if os.environ.get('ELIN_GAME_DIR'):
        return os.environ['ELIN_GAME_DIR']
    from steam_locate import find_game_dir
    g = find_game_dir()
    if g:
        print(f'自动定位游戏: {g}')
        return g
    raise SystemExit('找不到 Elin 安装目录：请传游戏目录参数，或用环境变量 ELIN_GAME_DIR')


GAME = _game_dir()
DRAMA = os.path.join(GAME, r"Package\_Lang_Chinese\Lang\CN\Dialog\Drama")
BIN = open(os.path.join(GAME, r"Elin_Data\sharedassets0.assets"), 'rb').read()

lang = lambda n: json.load(open(os.path.join(ROOT, 'data', 'lang', n + '.json'), encoding='utf-8'))
CHARA, RACE, JOB, ELEM = lang('Chara'), lang('Race'), lang('Job'), lang('Element')
raceCN = {k: v.get('name', '') for k, v in RACE.items()}
jobCN = {k: v.get('name', '') for k, v in JOB.items()}
elemCN = {k: v.get('name', '') for k, v in ELEM.items()}
elemAlias = {}
for k, v in ELEM.items():
    for f in ('alias', 'name_EN', 'name_JP'):
        a = v.get(f, '')
        if a:
            elemAlias[a.lower()] = v.get('name', '')
GENDER = {'f': '女性', 'm': '男性'}

def chara_row(cid):
    pat = bytes([len(cid)]) + b'\x00\x00\x00' + cid.encode()
    m = re.search(re.escape(pat), BIN)
    if not m:
        return []
    toks, p, end = [], m.start(), m.start() + 700
    while p < end:
        ln = struct.unpack('<i', BIN[p:p+4])[0]
        if 0 < ln < 80:
            s = BIN[p+4:p+4+ln]
            try:
                t = s.decode('utf-8')
                if t.isprintable():
                    toks.append(t); p = p+4+ln; p = (p+3) & ~3; continue
            except UnicodeDecodeError:
                pass
        toks.append(None); p += 4
    return [t for t in toks if t]

def parse_row(cid):
    s = chara_row(cid)
    race = next((x for x in s if x in raceCN), '')
    job = next((x for x in s if x in jobCN), '')
    sp = next((x for x in s if re.match(r'^[fm]/\d', x or '')), '')
    gender = GENDER.get(sp[:1], '') if sp else ''
    feats = [elemCN[x] for x in s if x.isdigit() and x in elemCN and 1200 <= int(x) <= 1999]
    abils = []
    for x in s:
        if '/' in x and not re.match(r'^[fm]/', x):
            for part in x.split('|'):
                a = part.split('/')[0]
                abils.append(elemAlias.get(a.lower(), a))
    return raceCN.get(race, ''), jobCN.get(job, ''), gender, feats, abils

def drama_lines(cid):
    p = os.path.join(DRAMA, cid + '.xlsx')
    if not os.path.exists(p):
        return []
    z = zipfile.ZipFile(p)
    s = z.read('xl/sharedStrings.xml').decode('utf-8', 'ignore')
    strs = re.findall(r'<t[^>]*>(.*?)</t>', s, re.S)
    sheet = z.read('xl/worksheets/sheet1.xml').decode('utf-8', 'ignore')
    rows = re.findall(r'<row[^>]*>(.*?)</row>', sheet, re.S)

    def rowmap(row):
        d = {}
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row, re.S):
            col, attrs, inner = m.group(1), m.group(2), m.group(3)
            if inner is None:
                d[col] = ''
                continue
            vm = re.search(r'<v>(.*?)</v>', inner, re.S)
            if not vm:
                d[col] = ''
                continue
            v = vm.group(1)
            d[col] = strs[int(v)] if 't="s"' in attrs else v
        return d

    if not rows:
        return []
    hdr = rowmap(rows[0])
    col_cn = next((c for c, v in hdr.items() if v == 'text'), None)
    col_en = next((c for c, v in hdr.items() if v == 'text_EN'), None)
    col_jp = next((c for c, v in hdr.items() if v == 'text_JP'), None)
    if not col_cn:
        return []
    out = []
    for r in rows[1:]:
        d = rowmap(r)
        v = (d.get(col_cn) or '').strip() or (d.get(col_en) or '').strip() or (d.get(col_jp) or '').strip()
        if v:
            out.append(v)
    return out[:6]

FILE2ID = {'缇克':'tyche','迪米塔斯':'demitas','波比':'poppy','拉斐尔':'raphael','索林':'sorin','VISHNU':'vishnu','穿布偶装的打工者':'parttimer_jure','赛特拉斯':'ineien','托兰':'guild_master_fighter','约格':'guild_master_mage','玛丽安':'guild_master_merchant','艾赫卡托尔':'ehekatl','机利亚':'adv_kiria','特菲拉':'vernis_boss','加雷斯':'doorman_wynan','斯塔莎':'stasha','雷托':'renton','莱布拉斯':'revlus','斯兰':'mapMerchant','乔南':'jonan','贾比':'xabi','埃夫隆德':'ephrond','贝里希':'barrich','盖罗克':'garokk','米拉尔':'miral','基尔巴德':'gilbert','艾露米纳雷':'eluminaire','卡多恩':'caldorn','摩安':'moyer'}

def main():
    outdir = os.path.join(ROOT, 'drafts', 'characters')
    for fn, cid in FILE2ID.items():
        row = CHARA.get(cid, {})
        cn = row.get('name', fn)
        en = row.get('name_EN', '')
        jp = row.get('name_JP', '')
        aka = row.get('aka', '')
        detail = row.get('detail', '')
        race_cn, job_cn, gender, feats, abils = parse_row(cid)
        lines = drama_lines(cid)
        os.makedirs(os.path.join(outdir, fn), exist_ok=True)
        old_path = os.path.join(outdir, fn, fn + '.md')
        old = open(old_path, encoding='utf-8').read() if os.path.exists(old_path) else ''
        m = re.search(r'\| genderCn[ \t]*=[ \t]*(\S*)', old)
        lv = re.search(r'\| levelCn[ \t]*=[ \t]*(\S*)', old)
        lv = lv.group(1) if lv and lv.group(1) != '|' else ''
        if m and m.group(1) != '|':
            gender = gender or m.group(1)
        w = []
        w.append('{{人物')
        w.append(f'| nameCn           =『{cn}』')
        w.append(f'| aliasCn          = {aka}')
        w.append(f'| genderCn         = {gender}')
        w.append(f'| raceCn           = {race_cn}')
        w.append(f'| classCn          = {job_cn}')
        if lv:
            w.append(f'| levelCn          = {lv}')
        w.append('}}')
        w.append('')
        if detail:
            w.append(f"'''{cn}'''（{en or jp}）{detail}")
        else:
            w.append(f"'''{cn}'''（{en or jp}）是一名角色。")
        w.append('')
        w.append('==角色面板==')
        w.append('====特性====')
        w.append('{| class="wikitable class-race"')
        w.append('!专长\n!描述\n!效果')
        if feats:
            for ft in feats:
                w.append(f'|-\n| {ft}\n| \n| ')
        else:
            w.append('|-\n| colspan="3" | 无')
        w.append('|}')
        w.append('')
        w.append('====能力/魔法====')
        if abils:
            for a in abils:
                w.append(f'* {a}')
        else:
            w.append('* 无')
        w.append('')
        w.append('====详细信息====')
        w.append('详细数值（属性/技能范围）待从游戏数据或 ylvapedia 补充。')
        w.append('')
        if lines:
            w.append('==台词==')
            w.append('{| class="wikitable"')
            w.append('!情境\n!台词')
            w.append('|-\n| 对话')
            for ln in lines:
                w.append(f'| 「{ln}」')
            w.append('|}')
            w.append('')
        w.append('==导航==')
        w.append('{{独特NPC}}')
        w.append('')
        w.append('[[分类:NPC]]')
        open(old_path, 'w', encoding='utf-8').write('\n'.join(w) + '\n')
        print('OK', fn, '|', race_cn, job_cn, gender, '| feats:', feats[:2], '| abils:', abils[:3])

if __name__ == '__main__':
    main()
