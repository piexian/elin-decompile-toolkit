"""pages：从工作区数据生成 wiki 草稿（角色表 / 角色页 / 地点页）。"""

import json
import re
import zipfile
from pathlib import Path

from .errors import ElinToolError, ExitCode
from .game_assets import find_game_dir

GENDER = {"f": "女性", "m": "男性"}


class PagesError(ElinToolError):
    """页面生成失败。"""

    exit_code = ExitCode.GAME_INCOMPLETE


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise PagesError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise PagesError(f"JSON 损坏 {path}：{e}") from e


def _read_jsonl(path: Path) -> list:
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as e:
        raise PagesError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise PagesError(f"JSONL 损坏 {path}：{e}") from e


def _require(workspace: Path, rel: str) -> Path:
    p = workspace / rel
    if not p.is_file():
        raise PagesError(f"缺 {rel}（先执行 data extract）：{workspace}")
    return p


# ---------------------------------------------------------------- chara-table

SHORT_MAP = {
    "Assassination": "Assassination",
    "Bath": "Bathing",
    "Cheer": "Cheering",
    "Chore": "Chores",
    "Clean": "Cleaning",
    "Cook": "Cooking",
    "Diary": "Diary",
    "Drug": "Drug",
    "Exercise": "Exercise",
    "Explore": "Exploration",
    "Farm": "Farming",
    "Fish": "Fishing",
    "Gacha": "Gacha",
    "Game": "Game",
    "History": "History",
    "Hoard": "Hoarding",
    "Hunt": "Hunting",
    "Lumberjack": "Lumberjack",
    "Nurse": "Nursing",
    "Paint": "Painting",
    "Pray": "Praying",
    "Read": "Reading",
    "Research": "Research",
    "Rich": "Extravagance",
    "Romance": "Romance",
    "Rumor": "Rumor",
    "Sing": "Singing",
    "Smith": "Blacksmith",
    "Supervising": "Supervising",
    "TreasureHunt": "Treasure Hunt",
}


def _reject_symlink(path: Path, what: str) -> None:
    """路径已是指向别处的符号链接时拒绝写入。"""
    if path.is_symlink():
        raise PagesError(f"{what}已是指向别处的符号链接，拒绝写入：{path}")


def _prepare_outdir(outdir: Path) -> None:
    """输出目录存在但不是目录或是指向别处的符号链接时拒绝；否则创建。"""
    if outdir.is_symlink() or (outdir.exists() and not outdir.is_dir()):
        raise PagesError(f"输出路径不是目录或是指向别处的符号链接，拒绝操作：{outdir}")
    try:
        outdir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise PagesError(f"创建输出目录失败 {outdir}：{e}") from e


def chara_table(workspace: Path, output: Path | None) -> Path:
    """用 charas_full.jsonl 重生成站内 [[角色表]] 的数据表（15 列）。"""
    outpath = output or workspace / "reports" / "pages" / "角色表-重生成.md"
    rows = _read_jsonl(_require(workspace, "data/charas_full.jsonl"))
    rows.sort(key=lambda r: r.get("_index", 0))
    C = _load_json(_require(workspace, "data/lang/Chara.json"))
    R = _load_json(_require(workspace, "data/lang/Race.json"))
    J = _load_json(_require(workspace, "data/lang/Job.json"))
    E = _load_json(_require(workspace, "data/lang/Element.json"))
    H = _load_json(_require(workspace, "data/lang/Hobby.json"))

    def norm(s):
        return (s or "").lower().replace("_", "").replace(" ", "")

    alias2cn = {}
    for k, e in E.items():
        for f in ("alias", "name_EN", "name_JP"):
            a = e.get(f) or ""
            if a:
                alias2cn.setdefault(norm(a), e.get("name"))
    el_id2cn = {}
    for er in _read_jsonl(_require(workspace, "data/elements.jsonl")):
        eid = er.get("id")
        cn = (E.get(str(eid), {}) or {}).get("name")
        if cn and cn != "*r":
            el_id2cn[er.get("alias")] = cn
    hobby_cn = {}
    for e in H.values():
        en = e.get("name_EN") or ""
        if en:
            hobby_cn[en] = e.get("name") or en
    raceCN = {k: (v.get("name") or k) for k, v in R.items()}
    jobCN = {k: (v.get("name") or k) for k, v in J.items()}
    for k in list(jobCN):
        if jobCN[k] == "*r":
            jobCN[k] = ""

    def name_of(cid):
        e = C.get(cid, {}) or {}
        cn = e.get("name") or ""
        if cn in ("", "*r"):
            return "随机"
        return cn

    def aka_of(cid):
        e = C.get(cid, {}) or {}
        a = e.get("aka") or ""
        return "" if a == "*r" else a

    def fmt_acts(r):
        out = []
        for a in r.get("actCombat") or []:
            parts = a.split("/")
            cn = el_id2cn.get(parts[0]) or alias2cn.get(norm(parts[0])) or parts[0]
            w = parts[1] if len(parts) > 1 else "100"
            out.append(f"{cn}{w}")
        return "、".join(out)

    def fmt_elements(r):
        els = r.get("elements") or []
        out = []
        for i in range(0, len(els) - 1, 2):
            eid, lv = els[i], els[i + 1]
            if not lv:
                continue
            cn = (E.get(str(eid), {}) or {}).get("name")
            if not cn or cn == "*r":
                cn = str(eid)
            out.append(f"{cn}{lv}")
        return "、".join(out)

    buf = [
        "<!-- 本表由 scripts pages chara-table 从工作区 data/charas_full.jsonl（SourceChara 全部行，"
        "严格解析自 sharedassets0.assets）重新生成，名字/别名/种族/职业/能力名均取 data/lang 官方语言包；"
        "`*r` 或空名显示「随机」。来源：data/charas_full.jsonl + data/lang/{Chara,Race,Job,Element,Hobby}.json -->",
        "来源：data/charas_full.jsonl + data/lang/{Chara,Race,Job,Element,Hobby}.json -->",
        "",
        '{| class="wikitable sortable"',
        "!id\n!名字\n!别名\n!默认等级\n!默认关系\n!标签\n!种族\n!职业\n!战斗模式\n!品级\n!先天能力\n!移动AI\n!默认战时行动及选取概率\n!默认工作\n!默认兴趣",
    ]
    for r in rows:
        cid = r["id"]
        ai = r.get("aiParam") or []
        ai_txt = f"目标距离{ai[0]},移动概率{ai[1]}" if len(ai) >= 2 else ""
        works = "、".join(
            hobby_cn.get(SHORT_MAP.get(w, w), w) for w in (r.get("works") or [])
        )
        hobbies = "、".join(
            hobby_cn.get(SHORT_MAP.get(h, h), h) for h in (r.get("hobbies") or [])
        )
        buf.append("|-")
        buf.append(
            "\n|\n".join(
                [
                    cid,
                    name_of(cid),
                    aka_of(cid),
                    str(r.get("LV", "")),
                    r.get("hostility") or "",
                    "、".join(r.get("tag") or []),
                    raceCN.get(r.get("race") or "", r.get("race") or ""),
                    jobCN.get(r.get("job") or "", r.get("job") or ""),
                    r.get("tactics") or "",
                    str(r.get("quality", "")),
                    fmt_elements(r),
                    ai_txt,
                    fmt_acts(r),
                    works,
                    hobbies,
                ]
            )
        )
    buf.append("|}")
    parent = outpath.parent
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise PagesError(f"输出路径不是目录或是指向别处的符号链接，拒绝操作：{parent}")
    if outpath.is_symlink():
        raise PagesError(f"输出文件已是指向别处的符号链接，拒绝写入：{outpath}")
    try:
        parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text("\n".join(buf) + "\n", encoding="utf-8")
    except OSError as e:
        raise PagesError(f"写出角色表失败 {outpath}：{e}") from e
    print(f"生成 {len(rows)} 行 -> {outpath}")
    return outpath


# ---------------------------------------------------------------- characters

# Drama 表 text 列为空的角色（正文在 action/param 列），不硬凑台词表
SKIP_DRAMA = {"casino_clerk"}

# 图片同源说明（核验发现的官方复用现象，写进稿内避免被当错误报）
IMG_NOTES = {
    "guild_doorman_mage": "官方立绘与战士公会守门人德利亚（guild_doorman_fighter）是同一张文件（游戏包内两文件 MD5 相同，官方复用）。",
    "guild_doorman_fighter": "官方立绘与魔法师公会守门人莱库萨斯（guild_doorman_mage）是同一张文件（游戏包内两文件 MD5 相同，官方复用）。",
    "mech_golem_a": "基础精灵与另一台魔甲兵威机（mech_golem_b）共用图集同一格（charas_full 两行 _tiles 均为 3），游戏内以不同配色区分。",
    "mech_golem_b": "基础精灵与另一台魔甲兵黑格斯（mech_golem_a）共用图集同一格（charas_full 两行 _tiles 均为 3），游戏内以不同配色区分。",
}

# 站内通行页名与角色 id 的对照
FILE2ID = {
    "缇克": "tyche",
    "迪米塔斯": "demitas",
    "波比": "poppy",
    "拉斐尔": "raphael",
    "索林": "sorin",
    "VISHNU": "vishnu",
    "穿布偶装的打工者": "parttimer_jure",
    "赛特拉斯": "ineien",
    "托兰": "guild_master_fighter",
    "约格": "guild_master_mage",
    "玛丽安": "guild_master_merchant",
    "艾赫卡托尔": "ehekatl",
    "机利亚": "adv_kiria",
    "特菲拉": "vernis_boss",
    "伽雷斯": "doorman_wynan",
    "斯塔莎": "stasha",
    "雷托": "renton",
    "莱布拉斯": "revlus",
    "斯兰": "mapMerchant",
    "乔南": "jonan",
    "贾比": "xabi",
    "埃夫隆德": "ephrond",
    "贝里希": "barrich",
    "盖罗克": "garokk",
    "米拉尔": "miral",
    "基尔巴德": "gilbert",
    "艾露米纳雷": "eluminaire",
    "卡多恩": "caldorn",
    "摩安": "moyer",
    "迷之幼女": "strange_girl",
    "拉纳莱": "larnneire",
    "班比": "minotaur_cook",
    "罗米阿斯": "lomias",
    "探求者": "seeker",
    "商人公会的女招待": "guild_clerk_merchant",
    "孤身一人…": "melilith_boss",
    "安茨拉西祖鲁": "azzrasizzle",
    "格里芬": "griffin",
    "梅尔文": "melvin",
    "比利": "billy",
    "艾莉莎": "erishe",
    "莱库萨斯": "guild_doorman_mage",
    "诺拉": "nola",
    "银猫": "cat_silver",
    "多伽": "doga",
    "威机": "mech_golem_b",
    "德内克": "denek",
    "德利亚": "guild_doorman_fighter",
    "怀那恩": "wynan",
    "战士公会的女招待": "guild_clerk_fighter",
    "沃格贡": "ungaga_pap",
    "泽茵": "zane",
    "科内利": "conery",
    "赌场女招待": "casino_clerk",
    "迪伯妮": "lurie_boss",
    "魔法师公会的女招待": "guild_clerk_mage",
    "黑格斯": "mech_golem_a",
    "被命名为「韦赛尔」的小狗": "dog_ves",
    "死者的代言人": "necromancer2",
    "沃卡加": "ungaga",
    "哥达": "orc_goda",
    "伊丝卡": "isca",
}


def _drama_lines(drama_dir: Path, cid: str) -> list:
    """读 Drama xlsx 的 text 列台词（CN 优先，EN/JP 兜底）。"""
    p = drama_dir / (cid + ".xlsx")
    if not p.is_file():
        return []
    try:
        with zipfile.ZipFile(p) as z:
            s = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
            strs = re.findall(r"<t[^>]*>(.*?)</t>", s, re.S)
            sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8", "ignore")
    except (OSError, zipfile.BadZipFile, KeyError) as e:
        raise PagesError(f"Drama 台词表损坏或缺少工作表 {p}：{e}") from e
    rows = re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S)

    def rowmap(row):
        d = {}
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row, re.S):
            col, attrs, inner = m.group(1), m.group(2), m.group(3)
            if inner is None:
                d[col] = ""
                continue
            vm = re.search(r"<v>(.*?)</v>", inner, re.S)
            if not vm:
                d[col] = ""
                continue
            v = vm.group(1)
            d[col] = strs[int(v)] if 't="s"' in attrs else v
        return d

    if not rows:
        return []
    hdr = rowmap(rows[0])
    col_cn = next((c for c, v in hdr.items() if v == "text"), None)
    col_en = next((c for c, v in hdr.items() if v == "text_EN"), None)
    col_jp = next((c for c, v in hdr.items() if v == "text_JP"), None)
    if not col_cn:
        return []
    out = []
    for r in rows[1:]:
        d = rowmap(r)
        v = (
            (d.get(col_cn) or "").strip()
            or (d.get(col_en) or "").strip()
            or (d.get(col_jp) or "").strip()
        )
        if v and not re.fullmatch(r"[A-Za-z_/]+", v):
            out.append(v)
    return out[:6]


def characters(workspace: Path, game, only: list) -> Path:
    """按「阿什兰德页」规格生成独特 NPC 角色页草稿。"""
    CHARA = _load_json(_require(workspace, "data/lang/Chara.json"))
    RACE = _load_json(_require(workspace, "data/lang/Race.json"))
    JOB = _load_json(_require(workspace, "data/lang/Job.json"))
    ELEM = _load_json(_require(workspace, "data/lang/Element.json"))
    raceCN = {k: v.get("name", "") for k, v in RACE.items()}
    jobCN = {k: v.get("name", "") for k, v in JOB.items()}
    elemAlias = {}
    for k, v in ELEM.items():
        for f in ("alias", "name_EN", "name_JP"):
            a = v.get(f, "")
            if a:
                elemAlias[a.lower()] = v.get("name", "")
    FULL = {r["id"]: r for r in _read_jsonl(_require(workspace, "data/charas_full.jsonl"))}

    if game:
        gdir = find_game_dir(game)
    else:
        gdir = find_game_dir(None)
    # Drama 台词目录：官方简中语言包的 Dialog/Drama（跨平台 pathlib 拼接）
    drama_dir = gdir / "Package" / "_Lang_Chinese" / "Lang" / "CN" / "Dialog" / "Drama"
    outdir = workspace / "reports" / "pages" / "characters"
    _prepare_outdir(outdir)

    only_set = set(only)
    count = 0
    for fn, cid in FILE2ID.items():
        if only_set and fn not in only_set and cid not in only_set:
            continue
        row = CHARA.get(cid, {})
        cn = row.get("name", fn) or ""
        if cn in ("", "*r"):
            cn = row.get("aka", "") or fn
        en = row.get("name_EN", "")
        jp = row.get("name_JP", "")
        aka = row.get("aka", "")
        detail = row.get("detail", "")
        full = FULL.get(cid, {})
        race_cn = raceCN.get(full.get("race") or "", "")
        job_cn = jobCN.get(full.get("job") or "", "")
        bio = full.get("bio") or ""
        seg = bio.split("|")[0].split("/")
        gender = GENDER.get(seg[0], "") if seg and seg[0] in GENDER else ""
        abils = [
            elemAlias.get(x.split("/")[0].lower(), x.split("/")[0])
            for x in (full.get("actCombat") or [])
        ]
        lines = [] if cid in SKIP_DRAMA else _drama_lines(drama_dir, cid)
        target = outdir / fn
        target.mkdir(parents=True, exist_ok=True)
        old_path = target / (fn + ".md")
        old = old_path.read_text(encoding="utf-8") if old_path.exists() else ""
        # 旧稿里人工填过的性别/等级保留
        m = re.search(r"\| genderCn[ \t]*=[ \t]*(\S*)", old)
        lv = re.search(r"\| levelCn[ \t]*=[ \t]*(\S*)", old)
        lv = lv.group(1) if lv and lv.group(1) != "|" else ""
        if m and m.group(1) != "|":
            gender = gender or m.group(1)
        w = []
        # 图片：优先官方立绘（Package/_Elona/Portrait/UN_<id>.png），否则像素小人
        # EN 名只有单个单词才用于文件名（短语式 name_EN 会生成带空格/引号的坏文件名）
        if en and en != "*r" and re.fullmatch(r"[A-Za-z]+", en):
            sprite_en = en
        else:
            sprite_en = "".join(p.capitalize() for p in cid.split("_"))
        sprite_fn = f"Elin_Npc_Sprite_{sprite_en}.png"
        portrait = gdir / "Package" / "_Elona" / "Portrait" / f"UN_{cid}.png"
        if portrait.is_file():
            img = f"[[File:UN_{cid}.png|left|200px]]<!--立绘：上传 Package/_Elona/Portrait/UN_{cid}.png，分类 立绘-->"
        else:
            img = f"[[File:{sprite_fn}|left|150px]]<!--像素小人：上传本文件夹的 {sprite_fn}，分类 Sprite-->"
        w.append("{{人物")
        w.append(f"| image            ={img}")
        w.append(f"| nameCn           =『{cn}』")
        w.append(f"| aliasCn          = {aka}")
        w.append(f"| genderCn         = {gender}")
        w.append(f"| raceCn           = {race_cn}")
        w.append(f"| classCn          = {job_cn}")
        if lv:
            w.append(f"| levelCn          = {lv}")
        w.append("}}")
        if cid in IMG_NOTES:
            w.append(f"<!-- {IMG_NOTES[cid]} -->")
        w.append("")
        if detail:
            w.append(f"'''{cn}'''（{en or jp}）{detail}")
        else:
            w.append(f"'''{cn}'''（{en or jp}）是一名角色。")
        w.append("")
        w.append("==角色面板==")
        w.append("====特性====")
        w.append('{| class="wikitable class-race"')
        w.append("!专长\n!描述\n!效果")
        w.append('|-\n| colspan="3" | 无')
        w.append("|}")
        w.append("")
        w.append("====能力/魔法====")
        if abils:
            for a in abils:
                w.append(f"* {a}")
        else:
            w.append("* 无")
        w.append("")
        w.append("====详细信息====")
        w.append("详细数值（属性/技能范围）待从游戏数据或 ylvapedia 补充。")
        w.append("")
        if lines:
            w.append("==台词==")
            w.append('{| class="wikitable"')
            w.append("!情境\n!台词")
            w.append("|-\n| 对话")
            for ln in lines:
                w.append(f"| 「{ln}」")
            w.append("|}")
            w.append("")
        w.append("==导航==")
        w.append("{{独特NPC}}")
        w.append("")
        w.append("[[分类:NPC]]")
        _reject_symlink(old_path, "角色页")
        try:
            old_path.write_text("\n".join(w) + "\n", encoding="utf-8")
        except OSError as e:
            raise PagesError(f"写出角色页失败 {old_path}：{e}") from e
        print("OK", fn, "|", race_cn, job_cn, gender, "| abils:", abils[:3])
        count += 1
    print(f"生成 {count} 个角色页 -> {outdir}")
    return outdir


# ---------------------------------------------------------------- zones

# 站内 模板:地点导航 缺失的页面标题 -> zone id
TITLE_MAP = {
    "帕罗米亚": "palmia",
    "卡普尔港": "kapul",
    "阿库里•提欧拉": "aquli",
    "好运金铃号": "casino",
    "特尔斐": "derphy",
    "诺耶尔": "noyel",
    "柳木堡": "lothria",
    "约恩": "yowyn",
    "涅芙村": "foxtown_nefu",
    "米芙村": "foxtown",
    "妹之馆": "house_sister",
    "赎罪之村": "village_exile",
    "鲁米艾斯特•环形山": "lumiest_ruin",
    "孤儿院": "asylum",
    "古城": "oldkeep",
    "巢穴": "void",
    "龙窟": "cave_dragon",
    "莱希墨苏": "lesimas",
    "小鬼洞穴": "cave_yeek",
    "小狗洞穴": "cave_puppy",
    "利萨纳斯": "lysanas",
    "尼米尔": "nymelle",
    "露里耶海底神殿": "temple_undersea",
    "牛头人巢穴": "cave_mino",
    "死者的洞窟": "cave_dead",
    "斗技场": "arena",
    "永久冻土": "snowgrave",
    "金字塔": "pyramid",
    "家居巨蛋": "housedome",
    "令人毛骨悚然的城": "chaos_castle",
    "山道": "cave_lerna",
    "莱纳": "larna",
    "韦尔尼斯": "vernis",
    "韦尔尼斯矿场": "vernis_mine",
    "机械遗迹": "dungeon_factory",
    "不归之森": "cave_fairy",
}

# 分组沿用站内地点导航模板：城镇 / 地城 / 特殊 / 未实装
GROUP = {
    "帕罗米亚": "城镇",
    "卡普尔港": "城镇",
    "阿库里•提欧拉": "城镇",
    "好运金铃号": "城镇",
    "特尔斐": "城镇",
    "诺耶尔": "城镇",
    "柳木堡": "城镇",
    "约恩": "城镇",
    "韦尔尼斯": "城镇",
    "涅芙村": "城镇",
    "米芙村": "城镇",
    "妹之馆": "城镇",
    "赎罪之村": "城镇",
    "鲁米艾斯特•环形山": "城镇",
    "孤儿院": "城镇",
    "古城": "城镇",
    "巢穴": "地城",
    "龙窟": "地城",
    "莱希墨苏": "地城",
    "小鬼洞穴": "地城",
    "小狗洞穴": "地城",
    "利萨纳斯": "地城",
    "尼米尔": "地城",
    "露里耶海底神殿": "地城",
    "牛头人巢穴": "地城",
    "死者的洞窟": "地城",
    "韦尔尼斯矿场": "地城",
    "机械遗迹": "地城",
    "不归之森": "地城",
    "斗技场": "特殊",
    "永久冻土": "特殊",
    "金字塔": "未实装",
    "家居巨蛋": "未实装",
    "令人毛骨悚然的城": "未实装",
    "山道": "未实装",
    "莱纳": "未实装",
}

# 委托 tag -> 站内 委托 页章节名
QUEST_TAG_CN = {
    "supply": "采购",
    "bulk": "大宗订单",
    "food": "烹饪",
    "deliver": "送货",
    "escort": "护卫",
    "farm": "收获",
    "music": "演出",
    "monster": "狩猎／剿灭",
    "war": "战争",
}

# 站内通行页名与官方译名不一致的对照（写进稿件提醒，发布者决定重定向方向）
TITLE_DIFF_NOTE = {
    "小狗洞穴": "官方译名为「小狗洞窟」（Puppy's Cave）",
    "山道": "官方译名为「山道入口」（Mountain Pass）",
    "莱纳": "官方译名为「莱娜」（Larna）",
    "阿库里•提欧拉": "官方译名使用间隔号「·」写作「阿库里·提欧拉」",
    "鲁米艾斯特•环形山": "官方译名使用间隔号「·」写作「鲁米艾斯特·环形山」",
}


def _zone_body(title, z, zone_lang, faction_lang):
    lang = zone_lang.get(z["id"])
    if not isinstance(lang, dict):
        raise PagesError(
            f"Zone.json 缺少 zone {z['id']!r}（页面 {title}），语言包与 zones_full 不一致"
        )
    group = GROUP[title]
    lines = [f"=={title}({lang.get('name_EN') or z['name']})==", "", "===基本信息==="]
    flavor = lang.get("textFlavor") or ""
    if flavor and flavor != "*r":
        lines.append(f'{{{{羊皮纸|"{flavor}"|收缩=是}}}}')
    lines.append("")
    lines.append(
        f"* '''官方名称'''：{lang.get('name')}（英文名 {lang.get('name_EN')}，日文名 {lang.get('name_JP')}）"
    )
    if title in TITLE_DIFF_NOTE:
        lines.append(
            f"* '''页面名说明'''：{TITLE_DIFF_NOTE[title]}，站内通行名为「{title}」，建议发布时建重定向统一。"
        )
    lines.append(f"* '''类型'''：{group}")
    parent = z["parent"]
    parent_cn = zone_lang.get(parent, {}).get("name") or parent or "—"
    lines.append(f"* '''所属区域'''：{parent_cn}")
    if z["faction"]:
        fac_cn = faction_lang.get(z["faction"], {}).get("name") or z["faction"]
        lines.append(f"* '''阵营'''：{fac_cn}")
    if z["LV"] > 1:
        lines.append(f"* '''危险度'''：{z['LV']}（世界地图显示的危险等级）")
    if z["pos"]:
        lines.append(f"* '''世界地图坐标'''：{z['pos'][0]}, {z['pos'][1]}（源码数值）")
    if z["idFile"]:
        lines.append(
            f"* '''地图文件'''：{'、'.join(z['idFile'])}（Package/_Elona/Map/）"
        )
    if lang.get("version"):
        lines.append(f"* '''条目版本'''：{lang['version']}（语言包标注的实装版本）")
    lines.append("")
    lines.append(
        "<!-- 来源：官方名称/风味文本/实装版本取自 data/lang/Zone.json；"
        "危险度/坐标/所属区域/阵营/地图文件取自 data/zones_full.json（SourceZone 行，严格解析自 sharedassets0.assets） -->"
    )
    lines.append("")

    quest_tags = [t for t in z["questTag"] if t]
    if quest_tags:
        lines.append("===委托倾向===")
        lines.append(
            "该地区居民在[[委托|告示板]]发布的委托类型有以下倾向（数值为源码权重，"
            "基准权重为 1，权重越高相对越常见；权重 0 表示该类型不会出现）："
        )
        lines.append("")
        lines.append('{| class="wikitable"')
        lines.append("! 委托类型 !! 权重")
        for qt in quest_tags:
            tag, _, wgt = qt.partition("/")
            tag_cn = QUEST_TAG_CN.get(tag, tag)
            lines.append("|-")
            lines.append(f"| [[委托#{tag_cn}|{tag_cn}]] || {wgt}")
        lines.append("|}")
        lines.append("")
        lines.append(
            "<!-- 来源：data/zones_full.json questTag 列；权重消费逻辑见反编译 Zone.cs TryGenerateQuests -->"
        )
        lines.append("")
    return lines


def _random_nefia(zone_lang, affix_lang):
    lines = ["==随机奈菲亚==", "", "===基本信息==="]
    lines.append(
        "随机奈菲亚指在世界地图上随机生成、每次进入布局与名称都会变化的野外地城，"
        "名称由前缀词缀与地形类型组合而成。"
    )
    lines.append("")
    lines.append("===地城词缀===")
    lines.append("以下是语言包中的全部地城词缀（官方中文译名）：")
    lines.append("")
    lines.append('{| class="wikitable sortable"')
    lines.append("! 词缀 !! 英文")
    for k in sorted(affix_lang, key=lambda x: int(x) if x.isdigit() else 999):
        e = affix_lang[k]
        name = e.get("name") or ""
        if not name or name == "*r":
            continue
        lines.append("|-")
        lines.append(f"| {name} || {e.get('name_EN') or ''}")
    lines.append("|}")
    lines.append("")
    lines.append(
        "<!-- 来源：data/lang/ZoneAffix.json（官方语言包）；"
        "地城生成机制见反编译 Zone_RandomDungeon 相关类 -->"
    )
    lines.append("")
    return lines


def zones(workspace: Path) -> Path:
    """按站内 模板:地点导航 的分组生成缺失地点页草稿。"""
    outdir = workspace / "reports" / "pages" / "zones"
    _prepare_outdir(outdir)
    zones = _load_json(_require(workspace, "data/zones_full.json"))
    zone_lang = _load_json(_require(workspace, "data/lang/Zone.json"))
    faction_lang = _load_json(_require(workspace, "data/lang/Faction.json"))
    affix_lang = _load_json(_require(workspace, "data/lang/ZoneAffix.json"))
    by_id = {z["id"]: z for z in zones}
    outdir.mkdir(parents=True, exist_ok=True)

    count = 0
    for title, zid in TITLE_MAP.items():
        z = by_id.get(zid)
        if z is None:
            print(f"!! zones_full.json 里没有 {zid}（页面 {title}）")
            continue
        lines = _zone_body(title, z, zone_lang, faction_lang)
        lines.append("===参见===")
        lines.append("* [[委托]]：委托类型与各城镇请求倾向")
        lines.append("* [[地区]]")
        lines.append("")
        lines.append("{{地点导航}}")
        lines.append("")
        lines.append("__NOREC__")
        lines.append("[[分类:地点]]")
        _reject_symlink(outdir / f"{title}.md", "地点页")
        try:
            (outdir / f"{title}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            raise PagesError(f"写出地点页失败 {outdir / (title + '.md')}：{e}") from e
        count += 1
    # 随机奈菲亚概念页
    lines = _random_nefia(zone_lang, affix_lang)
    lines.append("===参见===")
    lines.append("* [[奈菲亚]]")
    lines.append("* [[地城]]")
    lines.append("* [[地区]]")
    lines.append("")
    lines.append("{{地点导航}}")
    lines.append("")
    lines.append("__NOREC__")
    lines.append("[[分类:地点]]")
    lines.append("[[分类:奈菲亚]]")
    _reject_symlink(outdir / "随机奈菲亚.md", "地点页")
    try:
        (outdir / "随机奈菲亚.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        raise PagesError(f"写出地点页失败 {outdir / '随机奈菲亚.md'}：{e}") from e
    count += 1
    print(f"生成 {count} 个地点草稿 -> {outdir}")
    return outdir
