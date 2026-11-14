"""corpus build：把工作区数据渲染成 RAG 语料（每个实体一个 .md 小节）。"""

import json
import re
import shutil
from pathlib import Path

from .errors import GameIncompleteError

# 仓库源表：版本变动总表与人工考据知识随仓库发布，语料渲染直接读它们
REPO_DATA = Path(__file__).resolve().parent.parent / "data"

PLACEHOLDER = {"*r", "*", "-", "?", "　"}

LANG_TABLES = {
    "charas": "Chara",
    "elements": "Element",
    "materials": "Material",
    "categories": "Category",
    "zones": "Zone",
}


def _load_json(path: Path):
    """读取 JSON（utf-8-sig），OSError/坏 JSON 转 GameIncompleteError。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise GameIncompleteError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise GameIncompleteError(f"JSON 损坏 {path}：{e}") from e


def _read_jsonl(path: Path) -> list:
    """读取 JSONL，OSError/坏 JSON 转 GameIncompleteError。"""
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as e:
        raise GameIncompleteError(f"读取失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise GameIncompleteError(f"JSONL 损坏 {path}：{e}") from e
    bad = next((i for i, r in enumerate(rows) if not isinstance(r, dict)), None)
    if bad is not None:
        raise GameIncompleteError(f"JSONL 第 {bad + 1} 行不是对象：{path}")
    return rows


def _sanitize(name: str) -> str:
    name = re.sub(r"\s+", " ", name)
    return re.sub(r'[\\/:*?"<>|]', "_", name)[:80]


def _write(outdir: Path, name: str, text: str) -> None:
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / (_sanitize(name) + ".md")).write_text(text, encoding="utf-8")
    except OSError as e:
        raise GameIncompleteError(f"写出语料失败 {outdir}/{name}.md：{e}") from e


def is_placeholder(v) -> bool:
    """官方语言包对未翻译行会填 *r 等占位符。"""
    return (v or "").strip() in PLACEHOLDER


def build_lang_corpus(rows: dict, table: str, outdir: Path, base_fields=("name", "detail", "aka")) -> int:
    """生成语言表语料。

    官方 CN 语言包对未翻译的行在 name 列填 `*r` 占位符，真正的日文/英文名
    落在 name_JP / name_EN / detail_JP 等列。只导出中文列会把这些条目的名字
    全丢掉（Chara 表有 139/598 行属于这种情况），所以把所有 *_EN / *_JP 列
    都带出来，占位符本身换成可检索的说明。
    """
    n = 0
    for rid, row in rows.items():
        if not isinstance(row, dict):
            raise GameIncompleteError(f"语言包 {table}.json 的行 {rid!r} 不是对象")
        cn = row.get("name", "")
        alts = [
            row.get(k)
            for k in ("name_JP", "name_EN", "detail_JP", "detail_EN")
            if row.get(k) and not is_placeholder(row.get(k))
        ]
        if is_placeholder(cn):
            head = alts[0] if alts else "（待官方翻译）"
        else:
            head = cn or (alts[0] if alts else rid)
        parts = [f"# {head}（{table} id={rid}）", ""]
        for f in base_fields:
            v = row.get(f)
            if v and not is_placeholder(v):
                parts.append(f"- {f}: {v}")
        if is_placeholder(cn):
            parts.append("- 中文名: 官方未翻译（语言包占位符 *r）")
        for k in sorted(row):
            if not (k.endswith("_EN") or k.endswith("_JP")) or k in base_fields:
                continue
            v = row[k]
            if v and not is_placeholder(v):
                parts.append(f"- {k}: {v}")
        _write(outdir, f"{rid}_{head}", "\n".join(parts) + "\n")
        n += 1
    return n


def build_items(things: list, thing_lang: dict, outdir: Path) -> tuple[int, int]:
    """canonical things.jsonl 按 id 直接关联 Thing.json，禁止按名字猜 id。"""
    n = 0
    missing = 0
    for r in things:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str) or not r["id"]:
            raise GameIncompleteError("things.jsonl 里有一行缺少非空字符串 id 字段")
        rid = r["id"]
        lrow = thing_lang.get(rid, {})
        cn = lrow.get("name", "")
        cn_valid = cn if cn and not is_placeholder(cn) else ""
        parts = [f"# {cn_valid or r['name_en']}（物品 id={rid}）", ""]
        parts.append(f"- 英文名: {r['name_en']} / 日文名: {r['name_jp']}")
        if cn_valid:
            parts.append(f"- 中文名: {cn_valid}")
        if not lrow:
            parts.append("- id 不在官方语言包 Thing.json（待核对）")
            missing += 1
        parts.append(f"- 材质: {r.get('defMat') or ''} / 分类: {r.get('category') or ''}")
        if r.get("components") and r["components"] != ["-"]:
            parts.append(
                f"- 配方: {' + '.join(r['components'])} @ {'/'.join(r.get('factory') or [])}"
            )
        detail = lrow.get("detail") or ""
        if detail and not is_placeholder(detail):
            parts.append(f"- 描述: {detail}")
        _write(outdir, f"{rid}_{cn_valid or r['name_en']}", "\n".join(parts) + "\n")
        n += 1
    return n, missing


def build_versions(outdir: Path) -> int:
    """版本变动语料：渲染结构化源表 version_changes.json 与 data/knowledge/*.json。"""
    sources = [REPO_DATA / "version_changes.json"]
    knowledge = REPO_DATA / "knowledge"
    if knowledge.is_dir():
        sources += sorted(knowledge.glob("*.json"))
    nv = 0
    for sp in sources:
        if not sp.is_file():
            raise GameIncompleteError(f"仓库源表缺失：{sp}")
        doc = _load_json(sp)
        if not isinstance(doc, dict):
            raise GameIncompleteError(f"版本源表顶层必须是对象：{sp}")
        title = doc.get("topic") or "版本变动"
        if "versions" in doc:
            b = doc.get("baseline", {})
            overview = (
                "# 版本变动总览\n\n"
                f"- 当前基线: {b.get('version', '')}（{b.get('versionInt', '')}，"
                f"{b.get('channel', '')}，{b.get('buildDate', '')} 构建；"
                f"语料同步于 {b.get('syncedAt', '')}）\n"
                + "\n".join(
                    f"- {v['version']}（{v.get('date', '')}）："
                    + "；".join(sec["title"] for sec in v.get("sections", []))
                    for v in doc.get("versions", [])
                )
                + "\n"
            )
            _write(outdir, "版本总览", overview)
            nv += 1
            for v in doc.get("versions", []):
                parts = [f"# 版本变动：{v['version']}（{v.get('date', '')}）", ""]
                for sec in v.get("sections", []):
                    parts.append(f"## {sec['title']}")
                    parts += [f"- {pt}" for pt in sec.get("points", [])]
                    parts.append("")
                _write(outdir, f"版本变动_{v['version']}", "\n".join(parts) + "\n")
                nv += 1
        else:
            parts = [f"# {title}", ""]
            for sec in doc.get("sections", []):
                parts.append(f"## {sec['title']}")
                parts += [f"- {pt}" for pt in sec.get("points", [])]
                parts.append("")
            _write(outdir, title, "\n".join(parts) + "\n")
            nv += 1
    return nv


def build(workspace: Path) -> None:
    """构建 workspace/kb/corpus，先清空旧目录避免实体改名后留重复条目。"""
    data = workspace / "data"
    lang_dir = data / "lang"
    if not lang_dir.is_dir():
        raise GameIncompleteError(
            f"缺 data/lang（先执行 data extract --table lang）：{workspace}"
        )
    for f in ("things.jsonl", "things_full.jsonl"):
        if not (data / f).is_file():
            raise GameIncompleteError(f"缺 {f}（先执行 data extract）：{workspace}")
    out = workspace / "kb" / "corpus"
    if out.is_symlink() or (out.exists() and not out.is_dir()):
        raise GameIncompleteError(
            f"语料输出路径已存在且不是目录或是指向别处的符号链接，拒绝操作：{out}"
        )
    try:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
    except OSError as e:
        raise GameIncompleteError(f"准备语料目录失败 {out}：{e}") from e

    for folder, table in LANG_TABLES.items():
        rows = _load_json(lang_dir / f"{table}.json")
        if not isinstance(rows, dict):
            raise GameIncompleteError(f"语言包顶层必须是对象：{lang_dir / (table + '.json')}")
        print(f"{table}: {build_lang_corpus(rows, table, out / folder)} 节")

    things = _read_jsonl(data / "things.jsonl")
    thing_lang = _load_json(lang_dir / "Thing.json")
    items_n, missing = build_items(things, thing_lang, out / "items")
    print(f"items: {items_n} 节（{missing} 个 id 不在语言包）")

    nv = build_versions(out / "versions")
    print(f"versions: {nv} 节（version_changes.json 与 data/knowledge/*.json）")
    print(f"语料目录: {out}")
