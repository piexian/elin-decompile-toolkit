"""data extract：把官方语言包与 Source 表提取进版本工作区。"""

import argparse
import json
import sys
from pathlib import Path

from .. import extractors, game_assets, language
from ..errors import ElinToolError, GameIncompleteError, WorkspaceError
from ..extractors.core import (
    check_ids,
    extract_table,
    load_lang_ids,
    load_lang_table,
    write_json,
    write_rows,
)
from ..extractors.things import build_canonical, parse_thing_row


def _load_workspace(ws: Path) -> dict:
    """读取 version.json，返回登记信息。"""
    vj = ws / "version.json"
    if not ws.is_dir() or not vj.is_file():
        raise WorkspaceError(f"不是有效工作区（缺 version.json）：{ws}")
    try:
        return json.loads(vj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise WorkspaceError(f"version.json JSON 损坏 {vj}：{e}") from e
    except OSError as e:
        raise WorkspaceError(f"读取 version.json 失败 {vj}：{e}") from e


def _resolve_game_dir(info: dict, explicit: Path | None) -> Path:
    """游戏目录：--game > 工作区登记 > ELIN_GAME_DIR。"""
    if explicit:
        return game_assets.find_game_dir(explicit)
    gd = info.get("game_dir")
    if gd:
        game_dir = Path(gd)
        if not game_dir.is_dir():
            raise WorkspaceError(
                f"工作区登记的游戏目录不存在：{game_dir}（可用 --game 覆盖）"
            )
        return game_dir
    return game_assets.find_game_dir(None)


def _run_table(name: str, data: bytes, lang_dir: Path, data_dir: Path) -> str:
    """提取一张表：严格解析 → ID 校验 → 写输出，返回摘要行。"""
    cfg = extractors.TABLES[name]
    rows = cfg["extract"](data, lang_dir)
    lang_path = lang_dir / cfg["lang"]
    if not lang_path.is_file():
        raise GameIncompleteError(f"缺少语言包 {cfg['lang']}，先执行 data extract --table lang")
    lang_ids = load_lang_ids(
        lang_path,
        numeric=cfg.get("numeric", False),
        id_column=cfg.get("id_column", False),
    )
    note = check_ids(rows, lang_ids, cfg["ids"], cfg.get("allow", frozenset()))
    if cfg.get("allow"):
        extra = sorted(set(lang_ids) - {r["id"] for r in rows})
        if extra:
            note = (
                f"语言包含 {len(extra)} 个运行时生成的 ID（50100..51416，每组 0..16），"
                "非资产行，未写入"
            )
    if "row_build" in cfg:
        rows = cfg["row_build"](rows)
    if "lang_build" in cfg:
        lang_table = load_lang_table(lang_path)
        rows, legacy = cfg["lang_build"](rows, lang_table)
        write_json(data_dir / "materials.json", legacy)
    write_rows(data_dir / cfg["out"], rows, cfg["jsonl"])
    line = f"{name}: {len(rows)} 行 -> {cfg['out']}"
    if note:
        line += f"\n  {note}"
    return line


def _run_canonical(data: bytes, lang_dir: Path, data_dir: Path) -> str:
    """从严格 SourceThing 行生成 canonical things.jsonl 与 recipes.json。"""
    rows = extract_table(
        data, "SourceThing", parse_thing_row, (1000, 6000)
    )[0]
    things, recipes = build_canonical(rows)
    write_rows(data_dir / "things.jsonl", things, True)
    write_json(data_dir / "recipes.json", recipes)
    return f"canonical: things {len(things)} 行, recipes {len(recipes)} 条 -> things.jsonl / recipes.json"


def _run_extract(args: argparse.Namespace) -> int:
    """执行提取，返回退出码。"""
    info = _load_workspace(args.workspace)
    data_dir = args.workspace / "data"
    lang_dir = data_dir / "lang"
    game_dir = _resolve_game_dir(info, args.game)

    if args.all:
        targets = ["lang"] + extractors.TABLE_ORDER + ["canonical"]
    else:
        targets = args.table
        unknown = [t for t in targets if t not in ("lang", "canonical") and t not in extractors.TABLES]
        if unknown:
            raise ElinToolError(f"未知表名：{'、'.join(unknown)}（可选：lang、{'、'.join(extractors.TABLE_ORDER)}、canonical）")
        if not targets:
            raise ElinToolError("用 --all 或至少一个 --table 指定提取目标")

    data = None
    for t in targets:
        if t == "lang":
            counts = language.export_lang(game_assets.lang_cn_dir(game_dir), lang_dir)
            print(f"lang: {len(counts)} 个文件 -> {lang_dir}")
            continue
        if data is None:
            data = game_assets.read_assets(game_dir)
        if t == "canonical":
            print(_run_canonical(data, lang_dir, data_dir))
        else:
            print(_run_table(t, data, lang_dir, data_dir))
    return 0


def main(argv: list[str]) -> int:
    """data 命令入口，返回退出码。"""
    parser = argparse.ArgumentParser(prog="scripts data", description="提取官方数据")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("extract", help="提取语言包与 Source 表")
    p.add_argument("--workspace", required=True, type=Path, help="版本工作区目录")
    p.add_argument("--game", type=Path, default=None, help="Elin 游戏目录（默认取工作区登记或 ELIN_GAME_DIR）")
    p.add_argument("--all", action="store_true", help="提取语言包与全部表")
    p.add_argument("--table", action="append", default=[], help="指定表名，可重复")
    args = parser.parse_args(argv)
    try:
        return _run_extract(args)
    except ElinToolError as e:
        print(f"data extract 失败：{e}", file=sys.stderr)
        return e.exit_code
