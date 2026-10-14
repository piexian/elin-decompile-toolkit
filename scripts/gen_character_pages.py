#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按"阿什兰德页"规格生成角色页草稿。
数据源: SourceChara(二进制) + Chara.json(name/aka/detail) + Race/Job.json + Drama xlsx(CN台词)。
用法: python gen_character_pages.py [游戏目录]
      游戏目录也可用环境变量 ELIN_GAME_DIR 指定；缺省取 Steam 默认路径。
"""
import json, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _game_dir():
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
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

# 面板数据一律取自 charas_full.jsonl（tools/extract_chara_rows.py 严格解析 SourceChara），
# 不做自由字节扫描——裸串定位会撞上同名类名/相邻行（seeker 撞类表、dog_ves 带入
# fox_wild 的 tail_fox、billy 把以太抗性当技能，都是 2026-10-11 核验抓出的实例）。
FULL = {r['id']: r for r in map(json.loads, open(os.path.join(ROOT, 'data', 'charas_full.jsonl'), encoding='utf-8-sig'))}

def parse_row(cid):
    r = FULL.get(cid)
    if not r:
        return '', '', '', [], []
    race = raceCN.get(r.get('race') or '', '')
    job = jobCN.get(r.get('job') or '', '')
    bio = (r.get('bio') or '')
    seg = bio.split('|')[0].split('/')
    gender = GENDER.get(seg[0], '') if seg and seg[0] in GENDER else ''
    abils = []
    for x in r.get('actCombat') or []:
        a = x.split('/')[0]
        abils.append(elemAlias.get(a.lower(), a))
    return race, job, gender, [], abils

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
        if v and not re.fullmatch(r'[A-Za-z_/]+', v):
            out.append(v)
    return out[:6]

# Drama 表 text 列为空的角色（如赌场女招待，正文在 action/param 列），不硬凑台词表
SKIP_DRAMA = {'casino_clerk'}

# 图片同源说明（核验发现的官方复用现象，写进稿内避免被当错误报）
IMG_NOTES = {
    'guild_doorman_mage': '官方立绘与战士公会守门人德利亚（guild_doorman_fighter）是同一张文件（游戏包内两文件 MD5 相同，官方复用）。',
    'guild_doorman_fighter': '官方立绘与魔法师公会守门人莱库萨斯（guild_doorman_mage）是同一张文件（游戏包内两文件 MD5 相同，官方复用）。',
    'mech_golem_a': '基础精灵与另一台魔甲兵威机（mech_golem_b）共用图集同一格（charas_full 两行 _tiles 均为 3），游戏内以不同配色区分。',
    'mech_golem_b': '基础精灵与另一台魔甲兵黑格斯（mech_golem_a）共用图集同一格（charas_full 两行 _tiles 均为 3），游戏内以不同配色区分。',
}

FILE2ID = {'缇克':'tyche','迪米塔斯':'demitas','波比':'poppy','拉斐尔':'raphael','索林':'sorin','VISHNU':'vishnu','穿布偶装的打工者':'parttimer_jure','赛特拉斯':'ineien','托兰':'guild_master_fighter','约格':'guild_master_mage','玛丽安':'guild_master_merchant','艾赫卡托尔':'ehekatl','机利亚':'adv_kiria','特菲拉':'vernis_boss','伽雷斯':'doorman_wynan','斯塔莎':'stasha','雷托':'renton','莱布拉斯':'revlus','斯兰':'mapMerchant','乔南':'jonan','贾比':'xabi','埃夫隆德':'ephrond','贝里希':'barrich','盖罗克':'garokk','米拉尔':'miral','基尔巴德':'gilbert','艾露米纳雷':'eluminaire','卡多恩':'caldorn','摩安':'moyer',
           '迷之幼女':'strange_girl','拉纳莱':'larnneire','班比':'minotaur_cook','罗米阿斯':'lomias','探求者':'seeker','商人公会的女招待':'guild_clerk_merchant','孤身一人…':'melilith_boss','安茨拉西祖鲁':'azzrasizzle','格里芬':'griffin','梅尔文':'melvin','比利':'billy','艾莉莎':'erishe','莱库萨斯':'guild_doorman_mage','诺拉':'nola','银猫':'cat_silver','多伽':'doga','威机':'mech_golem_b','德内克':'denek','德利亚':'guild_doorman_fighter','怀那恩':'wynan','战士公会的女招待':'guild_clerk_fighter','沃格贡':'ungaga_pap','泽茵':'zane','科内利':'conery','赌场女招待':'casino_clerk','迪伯妮':'lurie_boss','魔法师公会的女招待':'guild_clerk_mage','黑格斯':'mech_golem_a','被命名为「韦赛尔」的小狗':'dog_ves'}

def main():
    outdir = os.path.join(ROOT, 'drafts', 'characters')
    only = set(sys.argv[1:])
    for fn, cid in FILE2ID.items():
        if only and fn not in only:
            continue
        row = CHARA.get(cid, {})
        cn = row.get('name', fn) or ''
        if cn in ('', '*r'):
            cn = row.get('aka', '') or fn
        en = row.get('name_EN', '')
        jp = row.get('name_JP', '')
        aka = row.get('aka', '')
        detail = row.get('detail', '')
        race_cn, job_cn, gender, feats, abils = parse_row(cid)
        lines = [] if cid in SKIP_DRAMA else drama_lines(cid)
        os.makedirs(os.path.join(outdir, fn), exist_ok=True)
        old_path = os.path.join(outdir, fn, fn + '.md')
        old = open(old_path, encoding='utf-8').read() if os.path.exists(old_path) else ''
        m = re.search(r'\| genderCn[ \t]*=[ \t]*(\S*)', old)
        lv = re.search(r'\| levelCn[ \t]*=[ \t]*(\S*)', old)
        lv = lv.group(1) if lv and lv.group(1) != '|' else ''
        if m and m.group(1) != '|':
            gender = gender or m.group(1)
        w = []
        # 图片：优先官方立绘（Package/_Elona/Portrait/UN_<id>.png），否则像素小人
        # EN 名只有单个单词才用于文件名（短语式 name_EN 会生成带空格/引号的坏文件名）
        if en and en != '*r' and re.fullmatch(r'[A-Za-z]+', en):
            sprite_en = en
        else:
            sprite_en = ''.join(p.capitalize() for p in cid.split('_'))
        sprite_fn = f'Elin_Npc_Sprite_{sprite_en}.png'
        portrait = os.path.join(GAME, 'Package', '_Elona', 'Portrait', f'UN_{cid}.png')
        if os.path.exists(portrait):
            img = f'[[File:UN_{cid}.png|left|200px]]<!--立绘：上传 Package/_Elona/Portrait/UN_{cid}.png，分类 立绘-->'
        else:
            img = (f'[[File:{sprite_fn}|left|150px]]<!--像素小人：上传本文件夹的 {sprite_fn}，分类 Sprite-->')
        w.append('{{人物')
        w.append(f'| image            ={img}')
        w.append(f'| nameCn           =『{cn}』')
        w.append(f'| aliasCn          = {aka}')
        w.append(f'| genderCn         = {gender}')
        w.append(f'| raceCn           = {race_cn}')
        w.append(f'| classCn          = {job_cn}')
        if lv:
            w.append(f'| levelCn          = {lv}')
        w.append('}}')
        if cid in IMG_NOTES:
            w.append(f'<!-- {IMG_NOTES[cid]} -->')
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
