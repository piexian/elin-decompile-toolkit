"""lookup：按 id/中文名/英文名/日文名 模糊检索工作区数据。"""

import json
from pathlib import Path

from .errors import ElinToolError, ExitCode

TABLES = ("all", "thing", "mat", "cat", "ele")
HIT_CAP_LANG = 30
HIT_CAP_THING = 20


class LookupError(ElinToolError):
    """查询输入或数据无效。"""

    exit_code = ExitCode.GAME_INCOMPLETE


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise LookupError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise LookupError(f"JSON 损坏 {path}：{e}") from e
    if not isinstance(data, dict):
        raise LookupError(f"JSON 顶层必须是对象：{path}")
    return data


def _read_jsonl(path: Path) -> list:
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as e:
        raise LookupError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise LookupError(f"JSONL 损坏 {path}：{e}") from e
    bad = next((i for i, r in enumerate(rows) if not isinstance(r, dict)), None)
    if bad is not None:
        raise LookupError(f"JSONL 第 {bad + 1} 行不是对象：{path}")
    return rows


def show_lang(table_name: str, rid, row: dict) -> None:
    cn = row.get("name", "")
    en = row.get("name_EN", "")
    jp = row.get("name_JP", "")
    print(f"  [{table_name}] id={rid} | CN={cn} | EN={en} | JP={jp}")
    for k in ("detail", "detail_EN", "filter", "version"):
        v = row.get(k)
        if v and not str(v).isdigit():
            print(f"      {k}: {str(v)[:100]}")


def search_lang(lang_dir: Path, kw: str, table: str | None = None) -> None:
    """在语言包各表按 id/name/name_EN/name_JP/alias 模糊查。"""
    kwl = kw.lower()
    hits = 0
    try:
        files = sorted(lang_dir.iterdir())
    except OSError as e:
        raise LookupError(f"遍历 data/lang 失败：{e}") from e
    for fn in files:
        if not fn.name.endswith(".json"):
            continue
        name = fn.stem
        if table and name != table:
            continue
        for rid, row in _load_json(fn).items():
            if not isinstance(row, dict):
                raise LookupError(f"语言包 {fn.name} 的行 {rid!r} 不是对象")
            fields = [
                rid,
                str(row.get("name", "")),
                str(row.get("name_EN", "")),
                str(row.get("name_JP", "")),
                str(row.get("alias", "")),
            ]
            if any(kwl in f.lower() for f in fields):
                show_lang(name, rid, row)
                hits += 1
                if hits > HIT_CAP_LANG:
                    print(f"  ... (截断, 前{HIT_CAP_LANG}条)")
                    return


def search_things(things: list, thing_lang: dict, kw: str) -> None:
    """检索 canonical things.jsonl：id 与语言包直连，不按名字猜 id。"""
    kwl = kw.lower()
    id2cn = {rid: row.get("name", "") for rid, row in thing_lang.items()}
    hits = 0
    for r in things:
        if not isinstance(r, dict):
            raise LookupError("things.jsonl 里有一行不是对象")
        rid = r.get("id", "")
        cn = id2cn.get(rid, "")
        names = [rid, cn, r.get("name_en", ""), r.get("name_jp", ""), r.get("category", "")]
        if not any(kwl in str(n).lower() for n in names):
            continue
        print(f"  [thing] {cn or r['name_en']} / {r['name_en']} / {r['name_jp']}  (id={rid})")
        print(f"      材质: {r.get('defMat')} / 分类: {r.get('category')}")
        if r.get("components"):
            print(f"      配方: {r['components']} @ {r.get('factory')}")
        hits += 1
        if hits > HIT_CAP_THING:
            print(f"  ... (截断, 前{HIT_CAP_THING}条)")
            return
    if not hits:
        print("  (无物品匹配)")


def search_materials(mats: list, kw: str) -> None:
    """检索 materials.jsonl（新格式列表：id/alias/cn/...）。"""
    kwl = kw.lower()
    for i, m in enumerate(mats):
        if not isinstance(m, dict):
            raise LookupError(f"materials.jsonl 第 {i + 1} 行不是对象")
        fields = [m.get("alias"), m.get("cn"), m.get("name_jp"), m.get("name_en"), m.get("id")]
        if any(kwl in str(v).lower() for v in fields):
            print(
                f"  [material] {m.get('alias')} | id={m.get('id')} | "
                f"CN={m.get('cn')} | JP={m.get('name_jp')} | EN={m.get('name_en')}"
            )


def lookup(workspace: Path, table: str, query: str) -> None:
    """按表检索工作区数据；table ∈ all/thing/mat/cat/ele。"""
    data = workspace / "data"
    lang_dir = data / "lang"
    if not lang_dir.is_dir():
        raise LookupError(f"缺 data/lang（先执行 data extract --table lang）：{workspace}")
    things = _read_jsonl(data / "things.jsonl") if table in ("all", "thing") else []
    thing_lang = _load_json(lang_dir / "Thing.json") if table in ("all", "thing") else {}
    if table == "ele":
        search_lang(lang_dir, query, table="Element")
    elif table == "cat":
        search_lang(lang_dir, query, table="Category")
    elif table == "thing":
        search_things(things, thing_lang, query)
    elif table == "mat":
        mats = _read_jsonl(data / "materials.jsonl")
        if not mats or not isinstance(mats[0], dict):
            raise LookupError("materials.jsonl 不是新格式列表（先执行 data extract --table materials）")
        search_materials(mats, query)
    else:
        search_lang(lang_dir, query)
        search_things(things, thing_lang, query)
        mats = _read_jsonl(data / "materials.jsonl")
        search_materials(mats, query)
