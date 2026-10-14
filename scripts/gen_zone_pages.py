#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按站内 模板:地点导航 的分组，为 wiki 缺失地点页生成基础草稿。
数据源：
  data/zones_full.json        SourceZone 行（tools/extract_zone_rows.py 提取）
  data/lang/Zone.json         官方三语名 / 风味文本 / 实装版本
  data/lang/Faction.json      阵营官方名
  data/lang/ZoneAffix.json    随机奈菲亚词缀官方名
页名以站内 模板:地点导航 的链接标题为准（红链标题）；官方译名写进信息栏，
两者不一致时在稿内注明，由发布者决定建重定向还是改链。
用法: python gen_zone_pages.py <输出目录>
产出: <输出目录>/<页面名>.md
"""
import json
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 站内 模板:地点导航 缺失的页面标题 -> zone id（对照 data/zones_full.json）
TITLE_MAP = {
    '帕罗米亚': 'palmia',
    '卡普尔港': 'kapul',
    '阿库里•提欧拉': 'aquli',
    '好运金铃号': 'casino',
    '特尔斐': 'derphy',
    '诺耶尔': 'noyel',
    '柳木堡': 'lothria',
    '约恩': 'yowyn',
    '涅芙村': 'foxtown_nefu',
    '米芙村': 'foxtown',
    '妹之馆': 'house_sister',
    '赎罪之村': 'village_exile',
    '鲁米艾斯特•环形山': 'lumiest_ruin',
    '孤儿院': 'asylum',
    '古城': 'oldkeep',
    '巢穴': 'void',
    '龙窟': 'cave_dragon',
    '莱希墨苏': 'lesimas',
    '小鬼洞穴': 'cave_yeek',
    '小狗洞穴': 'cave_puppy',
    '利萨纳斯': 'lysanas',
    '尼米尔': 'nymelle',
    '露里耶海底神殿': 'temple_undersea',
    '牛头人巢穴': 'cave_mino',
    '死者的洞窟': 'cave_dead',
    '斗技场': 'arena',
    '永久冻土': 'snowgrave',
    '金字塔': 'pyramid',
    '家居巨蛋': 'housedome',
    '令人毛骨悚然的城': 'chaos_castle',
    '山道': 'cave_lerna',
    '莱纳': 'larna',
}

# 分组沿用站内地点导航模板：城镇 / 地城 / 特殊 / 未实装
GROUP = {
    '帕罗米亚': '城镇', '卡普尔港': '城镇', '阿库里•提欧拉': '城镇', '好运金铃号': '城镇',
    '特尔斐': '城镇', '诺耶尔': '城镇', '柳木堡': '城镇', '约恩': '城镇',
    '涅芙村': '城镇', '米芙村': '城镇', '妹之馆': '城镇', '赎罪之村': '城镇',
    '鲁米艾斯特•环形山': '城镇', '孤儿院': '城镇', '古城': '城镇',
    '巢穴': '地城', '龙窟': '地城', '莱希墨苏': '地城', '小鬼洞穴': '地城',
    '小狗洞穴': '地城', '利萨纳斯': '地城', '尼米尔': '地城', '露里耶海底神殿': '地城',
    '牛头人巢穴': '地城', '死者的洞窟': '地城',
    '斗技场': '特殊', '永久冻土': '特殊',
    '金字塔': '未实装', '家居巨蛋': '未实装', '令人毛骨悚然的城': '未实装',
    '山道': '未实装', '莱纳': '未实装',
}

# 委托 tag -> 站内 委托 页章节名（对照 data/quests_full.json 的 tags 列验证）
QUEST_TAG_CN = {
    'supply': '采购', 'bulk': '大宗订单', 'food': '烹饪', 'deliver': '送货',
    'escort': '护卫', 'farm': '收获', 'music': '演出', 'monster': '狩猎／剿灭',
    'war': '战争',
}

# 站内通行页名与官方译名不一致的对照（写进稿件提醒，发布者决定重定向方向）
TITLE_DIFF_NOTE = {
    '小狗洞穴': '官方译名为「小狗洞窟」（Puppy\'s Cave）',
    '山道': '官方译名为「山道入口」（Mountain Pass）',
    '莱纳': '官方译名为「莱娜」（Larna）',
    '阿库里•提欧拉': '官方译名使用间隔号「·」写作「阿库里·提欧拉」',
    '鲁米艾斯特•环形山': '官方译名使用间隔号「·」写作「鲁米艾斯特·环形山」',
}


def load_json(*parts):
    with open(os.path.join(WORKSPACE, 'data', *parts), encoding='utf-8-sig') as f:
        return json.load(f)


def build_zone_body(title, z, zone_lang, faction_lang):
    lang = zone_lang[z['id']]
    group = GROUP[title]
    lines = []
    lines.append(f'=={title}({lang.get("name_EN") or z["name"]})==')
    lines.append('')
    lines.append('===基本信息===')
    flavor = lang.get('textFlavor') or ''
    if flavor and flavor != '*r':
        lines.append(f'{{{{羊皮纸|"{flavor}"|收缩=是}}}}')
    lines.append('')
    lines.append(f"* '''官方名称'''：{lang.get('name')}（英文名 {lang.get('name_EN')}，日文名 {lang.get('name_JP')}）")
    if title in TITLE_DIFF_NOTE:
        lines.append(f"* '''页面名说明'''：{TITLE_DIFF_NOTE[title]}，站内通行名为「{title}」，建议发布时建重定向统一。")
    lines.append(f"* '''类型'''：{group}")
    parent = z['parent']
    parent_cn = zone_lang.get(parent, {}).get('name') or parent or '—'
    lines.append(f"* '''所属区域'''：{parent_cn}")
    if z['faction']:
        fac_cn = faction_lang.get(z['faction'], {}).get('name') or z['faction']
        lines.append(f"* '''阵营'''：{fac_cn}")
    if z['LV'] > 1:
        lines.append(f"* '''危险度'''：{z['LV']}（世界地图显示的危险等级）")
    if z['pos']:
        lines.append(f"* '''世界地图坐标'''：{z['pos'][0]}, {z['pos'][1]}（源码数值）")
    if z['idFile']:
        lines.append(f"* '''地图文件'''：{'、'.join(z['idFile'])}（Package/_Elona/Map/）")
    if lang.get('version'):
        lines.append(f"* '''条目版本'''：{lang['version']}（语言包标注的实装版本）")
    lines.append('')
    lines.append('<!-- 来源：官方名称/风味文本/实装版本取自 data/lang/Zone.json；'
                 '危险度/坐标/所属区域/阵营/地图文件取自 data/zones_full.json'
                 '（SourceZone 行，tools/extract_zone_rows.py 提取自 sharedassets0.assets） -->')
    lines.append('')

    quest_tags = [t for t in z['questTag'] if t]
    if quest_tags:
        lines.append('===委托倾向===')
        lines.append('该地区居民在[[委托|告示板]]发布的委托类型有以下倾向（数值为源码权重，'
                     '基准权重为 1，权重越高相对越常见；权重 0 表示该类型不会出现）：')
        lines.append('')
        lines.append('{| class="wikitable"')
        lines.append('! 委托类型 !! 权重')
        for qt in quest_tags:
            tag, _, w = qt.partition('/')
            tag_cn = QUEST_TAG_CN.get(tag, tag)
            lines.append('|-')
            lines.append(f'| [[委托#{tag_cn}|{tag_cn}]] || {w}')
        lines.append('|}')
        lines.append('')
        lines.append('<!-- 来源：data/zones_full.json questTag 列；权重消费逻辑见 Zone.cs '
                     'TryGenerateQuests（Zone.cs L3972 读取 questTag、L4000 前后按权重加权随机）-->')
        lines.append('')
    return lines


def build_random_nefia(zone_lang, affix_lang):
    lines = []
    lines.append('==随机奈菲亚==')
    lines.append('')
    lines.append('===基本信息===')
    lines.append('随机奈菲亚指在世界地图上随机生成、每次进入布局与名称都会变化的野外地城，'
                 '名称由前缀词缀与地形类型组合而成。')
    lines.append('')
    lines.append('===地城词缀===')
    lines.append('以下是语言包中的全部地城词缀（官方中文译名）：')
    lines.append('')
    lines.append('{| class="wikitable sortable"')
    lines.append('! 词缀 !! 英文')
    for k in sorted(affix_lang, key=lambda x: int(x) if x.isdigit() else 999):
        e = affix_lang[k]
        name = e.get('name') or ''
        if not name or name == '*r':
            continue
        lines.append('|-')
        lines.append(f'| {name} || {e.get("name_EN") or ""}')
    lines.append('|}')
    lines.append('')
    lines.append('<!-- 来源：data/lang/ZoneAffix.json（官方语言包）；'
                 '地城生成机制见反编译 Zone_RandomDungeon 相关类 -->')
    lines.append('')
    return lines


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORKSPACE, 'drafts', '地点')
    os.makedirs(outdir, exist_ok=True)
    zones = load_json('zones_full.json')
    zone_lang = load_json('lang', 'Zone.json')
    faction_lang = load_json('lang', 'Faction.json')
    affix_lang = load_json('lang', 'ZoneAffix.json')
    by_id = {z['id']: z for z in zones}

    count = 0
    for title, zid in TITLE_MAP.items():
        z = by_id.get(zid)
        if z is None:
            print(f'!! zones_full.json 里没有 {zid}（页面 {title}）')
            continue
        lines = build_zone_body(title, z, zone_lang, faction_lang)
        lines.append('===参见===')
        lines.append('* [[委托]]：委托类型与各城镇请求倾向')
        lines.append('* [[地区]]')
        lines.append('')
        lines.append('{{地点导航}}')
        lines.append('')
        lines.append('__NOREC__')
        lines.append('[[分类:地点]]')
        path = os.path.join(outdir, f'{title}.md')
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines) + '\n')
        count += 1
    # 随机奈菲亚概念页
    lines = build_random_nefia(zone_lang, affix_lang)
    lines.append('===参见===')
    lines.append('* [[奈菲亚]]')
    lines.append('* [[地城]]')
    lines.append('* [[地区]]')
    lines.append('')
    lines.append('{{地点导航}}')
    lines.append('')
    lines.append('__NOREC__')
    lines.append('[[分类:地点]]')
    lines.append('[[分类:奈菲亚]]')
    with open(os.path.join(outdir, '随机奈菲亚.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    count += 1
    print(f'生成 {count} 个地点草稿 -> {outdir}')


if __name__ == '__main__':
    main()
