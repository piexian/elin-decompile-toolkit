"""官方神祇页面和 Ylvapedia 角色补充命令实现。"""

import re
from pathlib import Path

from . import wikitext, ylvapedia
from .errors import ElinToolError, ExitCode, WorkspaceError
from .pages import _load_json, _prepare_outdir, _reject_symlink


class EnrichmentError(ElinToolError):
    """补充数据映射或页面生成失败。"""

    exit_code = ExitCode.GAME_INCOMPLETE

def _plain(value: str) -> str:
    """把外部 wikitext 转为审阅表文本，保留原始文字内容。"""
    value = re.sub(r"<br\s*/?>", "<br>", value)
    value = value.replace("'''", "").replace("''", "")
    value = value.replace("<sub>", "").replace("</sub>", "")
    value = value.replace("<abbr>", "").replace("</abbr>", "")
    value = value.replace("|", "\\|")
    return value.strip()

def _element_text(elements: list[int], lang: dict) -> str:
    result = []
    for i in range(0, len(elements) - 1, 2):
        eid, value = elements[i : i + 2]
        name = lang.get(str(eid), {}).get("name") or str(eid)
        result.append(f"{name} {value}")
    return "、".join(result) or "无"


def _rewards(row: dict, chara_lang: dict, thing_lang: dict, category_lang: dict) -> list[dict]:
    result = []
    for raw in row.get("rewards", []):
        ids = raw.split("|")
        first = ids[0]
        first_data = chara_lang.get(first) or thing_lang.get(first) or {}
        result.append(
            {
                "id": first,
                "ids": ids,
                "name": first_data.get("name") or first,
                "name_EN": first_data.get("name_EN") or "",
                "name_JP": first_data.get("name_JP") or "",
            }
        )
    return result


def gods(workspace: Path, output: Path | None = None) -> Path:
    """从严格 SourceReligion 和官方语言包生成神祇/神仆页面草稿。"""
    rows = _load_json(workspace / "data" / "religions.json")
    if not isinstance(rows, list) or not rows:
        raise EnrichmentError("religions.json 必须是非空数组；先执行 data extract --table religions")
    religion_lang = _load_json(workspace / "data" / "lang" / "Religion.json")
    chara_lang = _load_json(workspace / "data" / "lang" / "Chara.json")
    thing_lang = _load_json(workspace / "data" / "lang" / "Thing.json")
    category_lang = _load_json(workspace / "data" / "lang" / "Category.json")
    element_lang = _load_json(workspace / "data" / "lang" / "Element.json")
    for table in (religion_lang, chara_lang, thing_lang, category_lang, element_lang):
        if not isinstance(table, dict):
            raise EnrichmentError("神页所需语言包顶层不是对象")
    out = output or workspace / "reports" / "pages" / "gods"
    _prepare_outdir(out)
    count = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise EnrichmentError("religions.json 存在缺少 id 的行")
        rid = row["id"]
        lang = religion_lang.get(rid, {})
        if not isinstance(lang, dict) or not lang:
            raise EnrichmentError(f"Religion.json 缺少 {rid}")
        cn = lang.get("name") or row.get("name") or rid
        if str(cn).startswith("*"):
            cn = row.get("name") or rid
        lines = [f"=={cn}==", "", "===基本信息===", ""]
        lines.append(f"* '''官方名称'''：{cn}（英文名 {lang.get('name_EN') or ''}，日文名 {lang.get('name_JP') or ''}）")
        lines.append(f"* '''类型'''：{lang.get('textType') or row.get('textType') or '—'}")
        lines.append(f"* '''领域'''：{row.get('domain') or '—'}")
        lines.append(f"* '''信仰'''：{row.get('faith') or '—'}")
        lines.append(f"* '''祭坛材质'''：{row.get('idMaterial') or '—'}")
        if lang.get("detail"):
            lines += ["", lang["detail"]]
        lines += [
            "",
            "<!-- 来源：官方名称、类型和背景取 workspace/data/lang/Religion.json id=" + rid + "；领域、信仰、祭坛材质取 workspace/data/religions.json SourceReligion 行 -->",
            "",
            "===信仰加成===",
            "",
        ]
        benefit = lang.get("textBenefit") or row.get("textBenefit")
        if benefit:
            lines.append(benefit)
        lines.append(f"* 基础属性/技能成长：{_element_text(row.get('elements', []), element_lang)}")
        lines += [
            "",
            "<!-- 来源：信仰描述取 workspace/data/lang/Religion.json textBenefit；成长 ID/数值取 workspace/data/religions.json elements，中文名取 Element.json -->",
            "",
            "===供物===",
            "",
        ]
        offers = row.get("cat_offer") or []
        if offers:
            for category in offers:
                name = category_lang.get(category, {}).get("name") or category
                lines.append(f"* {name}（{category}）")
        else:
            lines.append("* 无")
        lines += [
            "",
            "<!-- 来源：供物类别取 workspace/data/religions.json cat_offer；官方中文名取 workspace/data/lang/Category.json -->",
            "",
            "===神仆与神器===",
            "",
        ]
        rewards = _rewards(row, chara_lang, thing_lang, category_lang)
        if rewards:
            for reward in rewards:
                extra = f"（候选 ID：{', '.join(reward['ids'])}）" if len(reward["ids"]) > 1 else ""
                lines.append(f"* {reward['name']}（{reward['id']}）{extra}")
        else:
            lines.append("* 无")
        lines += [
            "",
            "<!-- 来源：奖励 ID 取 workspace/data/religions.json rewards；神仆/神器中文名分别取官方 Chara.json/Thing.json；并列 ID 保留供核对 -->",
            "",
            "==导航==",
            "",
            "{{神导航}}",
            "",
            "[[分类:神]]",
        ]
        path = out / f"{cn}.md"
        _reject_symlink(path, "神祇页")
        try:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            raise WorkspaceError(f"写出神祇页失败 {path}：{e}") from e
        count += 1
    print(f"生成 {count} 个神祇/神仆页草稿 -> {out}")
    return out


def _unique_page(workspace: Path) -> dict:
    cache_dir = workspace / "ylvapedia" / "cache"
    for path in sorted(cache_dir.glob("Elin_Bestiary_Unique_NPCs-*.json")):
        if not path.name.endswith(".revisions.json"):
            return ylvapedia.load_cache(path)
    raise EnrichmentError("缺 Ylvapedia Unique_NPCs 缓存，先执行 ylvapedia fetch --page Elin:Bestiary/Unique_NPCs")




def enrich_characters(
    workspace: Path, ids: list[str], output: Path | None = None
) -> Path:
    """从 Ylvapedia 补充角色数据；输出审阅稿，不覆盖官方页面。"""
    if not ids:
        raise EnrichmentError("至少指定一个角色 ID")
    cache = _unique_page(workspace)
    entries = wikitext.unique_npcs(cache["wikitext"])
    by_id = {entry["link_id"].lower(): entry for entry in entries}
    chara_lang = _load_json(workspace / "data" / "lang" / "Chara.json")
    official_ids = set(chara_lang)
    out = output or workspace / "reports" / "enrichment" / "ylvapedia"
    _prepare_outdir(out)
    for cid in ids:
        if cid not in official_ids:
            raise EnrichmentError(f"官方 Chara.json 没有角色 ID：{cid}")
        entry = by_id.get(cid.lower())
        if entry is None:
            raise EnrichmentError(f"Ylvapedia Unique_NPCs 没有角色链接 ID：{cid}")
        official = chara_lang[cid]
        lines = [
            f"# {official.get('name') or cid}（Ylvapedia 补充审阅稿）",
            "",
            f"来源页面：[{cache['page']}]({cache['url']})",
            f"修订：{cache.get('revid') or '未知'}；抓取时间：{cache.get('fetched_at') or '未知'}",
            "",
            "本文件是外部补充，不覆盖官方语言包或 SourceChara 字段。",
            "",
            "| 字段 | 官方数据 | Ylvapedia 原文 |",
            "|---|---|---|",
            f"| ID | {cid} | {entry['link_id']} |",
            f"| 中文名 | {official.get('name') or ''} | {_plain(entry['Name'])} |",
            f"| 等级 | 以 SourceChara 为准 | {_plain(entry['Level'])} |",
            f"| 种族 | 以 SourceChara 为准 | {_plain(entry['Race'])} |",
            f"| 职业 | 以 SourceChara 为准 | {_plain(entry['Class'])} |",
            f"| 敌对性 | 以 SourceChara 为准 | {_plain(entry['Animosity'])} |",
            f"| 法术/能力 | 以 SourceChara 为准 | {_plain(entry['Spells/Abilities'])} |",
            f"| 专长 | 以 SourceChara 为准 | {_plain(entry['Feats'])} |",
            f"| AI | 以 SourceChara 为准 | {_plain(entry['AI'])} |",
            f"| 备注 | 官方表无此字段 | {_plain(entry['Notes'])} |",
            "",
            f"<!-- 来源：Ylvapedia {cache['page']}，revid={cache.get('revid')}；仅用于外部补充，不覆盖官方中文名和本地数据 -->",
        ]
        path = out / f"{cid}.md"
        _reject_symlink(path, "Ylvapedia 补查稿")
        try:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            raise WorkspaceError(f"写出 Ylvapedia 补查稿失败 {path}：{e}") from e
        print(f"已补充 {cid} -> {path}")
    return out
