"""SourceMaterial 行解析与链式提取（matColor/altColor 不在序列化流里）。"""

import struct

from ..binary import BinaryCursor, ParseError
from ..errors import GameIncompleteError

# (字段名, 类型)；类型 i=int, s=string, ia=int[], sa=string[]
FIELDS = [
    ("_index", "i"),
    ("id", "i"),
    ("alias", "s"),
    ("name_JP", "s"),
    ("name", "s"),
    ("category", "s"),
    ("tag", "sa"),
    ("thing", "s"),
    ("goods", "sa"),
    ("minerals", "sa"),
    ("decal", "i"),
    ("decay", "i"),
    ("grass", "i"),
    ("defFloor", "i"),
    ("defBlock", "i"),
    ("edge", "i"),
    ("ramp", "i"),
    ("idSound", "s"),
    ("soundFoot", "s"),
    ("hardness", "i"),
    ("groups", "sa"),
    ("tier", "i"),
    ("chance", "i"),
    ("weight", "i"),
    ("value", "i"),
    ("quality", "i"),
    ("atk", "i"),
    ("dmg", "i"),
    ("dv", "i"),
    ("pv", "i"),
    ("dice", "i"),
    ("bits", "sa"),
    ("elements", "ia"),
    ("altName", "sa"),
    ("altName_JP", "sa"),
]


def parse_row(c: BinaryCursor) -> dict:
    """按 FIELDS 声明序解析一行。"""
    row = {}
    for name, typ in FIELDS:
        if typ == "i":
            row[name] = c.int()
        elif typ == "s":
            row[name] = c.string()
        elif typ == "ia":
            row[name] = c.int_array(64)
        else:
            row[name] = c.str_array(64)
    return row


def find_table_start(data: bytes) -> int:
    """首行锚 process(id=94) 行向前回溯到 _index<=0；不能锚 'plain'（SourceZone 也有同名行）。"""
    i = 0
    while True:
        i = data.find(b"\x07\x00\x00\x00process", i + 1)
        if i < 0:
            raise GameIncompleteError("找不到材质表起点（process 行）")
        a, b = struct.unpack("<ii", data[i - 8 : i])
        if (a, b) != (94, 94):
            continue
        cur = i - 8
        starts = []
        while cur > 0 and len(starts) < 200:
            hit = None
            for back in range(4, 1024, 4):
                off = cur - back
                if off < 0:
                    break
                try:
                    c = BinaryCursor(data, off)
                    row = parse_row(c)
                except (ParseError, UnicodeDecodeError, struct.error):
                    continue
                if c.p == cur:
                    hit = (off, row)
                    break
            if not hit:
                break
            starts.append(hit)
            cur = hit[0]
            if hit[1]["_index"] <= 0:
                return cur
        return -1


def extract(data: bytes) -> list[dict]:
    """链式解析整张材质表：行间最多垫 1 个 int，对象边界向 64KB 内对齐扫描续接。"""
    start = find_table_start(data)
    if start < 0:
        raise GameIncompleteError("找不到材质表起点（plain 行）")
    rows = []
    off, prev = start, None
    while off < len(data) - 100:
        try:
            c = BinaryCursor(data, off)
            row = parse_row(c)
        except (ParseError, UnicodeDecodeError, struct.error):
            break
        p = c.p
        if prev is not None and row["_index"] != prev:
            break
        rows.append(row)
        prev = row["_index"] + 1
        nxt = None
        for pad in (0, 4):
            if p + pad + 8 <= len(data):
                a, b = struct.unpack("<ii", data[p + pad : p + pad + 8])
                if a == prev and 0 <= b < 600:
                    nxt = p + pad
                    break
        if nxt is None:
            limit = min(p + 65536, len(data) - 100)
            for q in range(p, limit, 4):
                try:
                    c2 = BinaryCursor(data, q)
                    g = parse_row(c2)
                except (ParseError, UnicodeDecodeError, struct.error):
                    continue
                if (
                    g["_index"] == prev
                    and g["alias"].isascii()
                    and g["alias"].isprintable()
                ):
                    nxt = q
                    break
        if nxt is None:
            break
        off = nxt
    if not rows:
        raise GameIncompleteError("材质表解析出 0 行")
    return rows


def build_outputs(rows: list, lang: dict) -> tuple[list, dict]:
    """生成 materials.jsonl 行（带简中名）与 legacy materials.json 映射。"""
    cn_by_id = {int(k): v for k, v in lang.items()}
    out = []
    for r in rows:
        lang_row = cn_by_id.get(r["id"], {})
        bits = r["bits"] or []
        out.append(
            {
                "id": r["id"],
                "alias": r["alias"],
                "name_en": r["name"],
                "name_jp": r["name_JP"],
                "cn": lang_row.get("name", ""),
                "prefix_cn": lang_row.get("altName", ""),
                "category": r["category"],
                "tag": r["tag"] or [],
                "thing": r["thing"],
                "hardness": r["hardness"],
                "tier": r["tier"],
                "weight": r["weight"],
                "value": r["value"],
                "quality": r["quality"],
                "chance": r["chance"],
                "atk": r["atk"],
                "dmg": r["dmg"],
                "dv": r["dv"],
                "pv": r["pv"],
                "dice": r["dice"],
                "bits": bits,
                "groups": r["groups"],
                "elements": r["elements"],
                "altName": r["altName"],
                "altName_JP": r["altName_JP"],
                "fireproof": "fire" in bits,
                "acidproof": "acid" in bits,
                "decay": r["decay"],
            }
        )
    legacy = {
        r["alias"]: {"id": r["id"], "jp": r["name_jp"], "en": r["name_en"], "cn": r["cn"]}
        for r in out
    }
    return out, legacy
