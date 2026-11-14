"""共用整表提取：对象头扫描、_index 链式校验、语言包 ID 校验与输出。"""

import json
import struct
from pathlib import Path

from ..binary import BinaryCursor, ParseError
from ..errors import GameIncompleteError, WorkspaceError
from ..game_assets import iter_table_headers


def extract_table(data: bytes, name: str, parse, count_range: tuple[int, int]) -> tuple[list, str]:
    """按对象头候选逐个尝试严格解析整表，要求 _index 连续，返回 (rows, 源 xlsx 名)。"""
    err = None
    for pos in iter_table_headers(data, name):
        try:
            c = BinaryCursor(data, pos)
            c.align()
            c.int()  # SourceData 头部 int
            c.string()  # 编辑器名
            src = c.string()  # 源 xlsx 文件名
            if not src.endswith(".xlsx"):
                continue
            count = c.int()
            if not count_range[0] <= count <= count_range[1]:
                continue
            rows = []
            while len(rows) < count:
                row = parse(c)
                if row["_index"] != len(rows):
                    raise ParseError(f"_index 不连续: {row['_index']} != {len(rows)}", c.p)
                rows.append(row)
            return rows, src
        except (ParseError, UnicodeDecodeError, struct.error) as e:
            err = e
    raise ParseError(f"{name}: 整表解析失败（{err}）", 0)


def load_lang_table(path: Path) -> dict:
    """读取语言包 JSON，IO 或解析失败转 GameIncompleteError。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise GameIncompleteError(f"读取语言包失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise GameIncompleteError(f"语言包 JSON 损坏 {path}：{e}") from e


def load_lang_ids(path: Path, numeric: bool = False, id_column: bool = False) -> set:
    """语言包 JSON → ID 集合（键、数字键或行内 id 列）。"""
    table = load_lang_table(path)
    if id_column:
        try:
            return {int(row["id"]) for row in table.values()}
        except (KeyError, TypeError, ValueError) as e:
            raise GameIncompleteError(f"语言包行缺少可解析的 id 列 {path}：{e}") from e
    if numeric:
        try:
            return {int(k) for k in table}
        except ValueError as e:
            raise GameIncompleteError(f"语言包键不是数字 {path}：{e}") from e
    return set(table)


def check_ids(
    rows: list, lang_ids: set, mode: str = "equal", allow: set = frozenset()
) -> str | None:
    """行 ID 与语言包集合校验；equal 不一致即抛错，warn 只返回警告。"""
    row_ids = [r["id"] for r in rows]
    allowed = set(lang_ids) | set(allow)
    missing = [i for i in row_ids if i not in allowed]
    if mode == "warn":
        if missing:
            return f"!! {len(missing)} 个 id 不在语言包: {missing[:8]}"
        return None
    if missing:
        raise GameIncompleteError(f"行 ID 与语言包不一致（缺 {missing[:8]}）")
    extra = sorted(set(lang_ids) - set(row_ids) - set(allow))
    if extra:
        raise GameIncompleteError(f"行 ID 与语言包不一致（多 {extra[:8]}）")
    return None


def write_rows(path: Path, rows: list, jsonl: bool) -> None:
    """jsonl 逐行写，否则缩进 1 的 JSON 数组，均 ensure_ascii=False。"""
    payload = (
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        if jsonl
        else json.dumps(rows, ensure_ascii=False, indent=1)
    )
    try:
        path.write_text(payload, encoding="utf-8")
    except OSError as e:
        raise WorkspaceError(f"写出失败 {path}：{e}") from e


def write_json(path: Path, obj) -> None:
    """写缩进 1 的 JSON 文件，失败转 WorkspaceError。"""
    try:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        raise WorkspaceError(f"写出失败 {path}：{e}") from e
