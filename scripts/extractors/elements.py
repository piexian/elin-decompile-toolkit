"""SourceElement 行解析与链式提取（_L 扩展列不在流里，elementMap 不序列化）。"""

import struct

from ..binary import BinaryCursor, ParseError
from ..errors import GameIncompleteError

# (字段名, 类型)；类型 i=int, f=float32, s=string, ia=int[], sa=string[]
FIELDS = [
    ("_index", "i"),
    ("id", "i"),
    ("alias", "s"),
    ("name_JP", "s"),
    ("name", "s"),
    ("altname_JP", "s"),
    ("altname", "s"),
    ("aliasParent", "s"),
    ("aliasRef", "s"),
    ("aliasMtp", "s"),
    ("parentFactor", "f"),
    ("lvFactor", "i"),
    ("encFactor", "i"),
    ("encSlot", "s"),
    ("mtp", "i"),
    ("LV", "i"),
    ("chance", "i"),
    ("value", "i"),
    ("cost", "ia"),
    ("geneSlot", "i"),
    ("sort", "i"),
    ("target", "s"),
    ("proc", "sa"),
    ("type", "s"),
    ("group", "s"),
    ("category", "s"),
    ("categorySub", "s"),
    ("abilityType", "sa"),
    ("tag", "sa"),
    ("thing", "s"),
    ("eleP", "i"),
    ("cooldown", "i"),
    ("charge", "i"),
    ("radius", "f"),
    ("max", "i"),
    ("req", "sa"),
    ("idTrainer", "s"),
    ("partySkill", "i"),
    ("tagTrainer", "s"),
    ("levelBonus_JP", "s"),
    ("levelBonus", "s"),
    ("foodEffect", "sa"),
    ("langAct", "sa"),
    ("detail_JP", "s"),
    ("detail", "s"),
    ("textPhase_JP", "s"),
    ("textPhase", "s"),
    ("textExtra_JP", "s"),
    ("textExtra", "s"),
    ("textInc_JP", "s"),
    ("textInc", "s"),
    ("textDec_JP", "s"),
    ("textDec", "s"),
    ("textAlt_JP", "sa"),
    ("textAlt", "sa"),
    ("adjective_JP", "sa"),
    ("adjective", "sa"),
]

# 反编译 SourceElement 在运行时生成的元素：14 组（50100..51400，步进 100），每组 0..16，
# 只存在于语言包，不在序列化资产行里
RUNTIME_ID_BASES = range(50100, 51500, 100)
RUNTIME_IDS_PER_GROUP = 17
RUNTIME_IDS = {b + o for b in RUNTIME_ID_BASES for o in range(RUNTIME_IDS_PER_GROUP)}

OUT_KEYS = [
    "id",
    "alias",
    "group",
    "name_en",
    "name_jp",
    "encSlot",
    "encFactor",
    "lvFactor",
    "mtp",
    "LV",
    "chance",
    "value",
    "cost",
    "geneSlot",
    "sort",
    "target",
    "proc",
    "type",
    "category",
    "categorySub",
    "abilityType",
    "tag",
    "thing",
    "eleP",
    "max",
    "req",
    "idTrainer",
    "detail_jp",
    "detail_en",
]


def parse_row(c: BinaryCursor) -> dict:
    """按 FIELDS 声明序解析一行。"""
    row = {}
    for name, typ in FIELDS:
        if typ == "i":
            row[name] = c.int()
        elif typ == "f":
            row[name] = c.float()
        elif typ == "s":
            row[name] = c.string()
        elif typ == "ia":
            row[name] = c.int_array(64)
        else:
            row[name] = c.str_array(64)
    return row


def find_table_start(data: bytes) -> int:
    """_void 行：[int 0][int 0][len 5]'_void'。"""
    i = 0
    while True:
        i = data.find(b"\x05\x00\x00\x00_void", i + 1)
        if i < 0:
            raise GameIncompleteError("找不到元素表起点（_void 行）")
        if struct.unpack("<ii", data[i - 8 : i]) == (0, 0):
            return i - 8


def extract(data: bytes) -> list[dict]:
    """从 _void 行起链式解析，按 _index 连续递增且行尾 pad=0 断开。"""
    rows = []
    off, prev = find_table_start(data), -1
    while off < len(data) - 100:
        try:
            c = BinaryCursor(data, off)
            row = parse_row(c)
            pad = c.int()
        except (ParseError, UnicodeDecodeError, struct.error):
            break
        if row["_index"] != prev + 1 or pad != 0:
            break
        rows.append(row)
        prev = row["_index"]
        off = c.p
    if not rows:
        raise GameIncompleteError("元素表解析出 0 行")
    return rows


def build_outputs(rows: list) -> list[dict]:
    """按 OUT_KEYS 生成 elements.jsonl 行；动态生成的元素不在资产行里。"""
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "alias": r["alias"],
                "group": r["group"],
                "name_en": r["name"],
                "name_jp": r["name_JP"],
                "encSlot": r["encSlot"],
                "encFactor": r["encFactor"],
                "lvFactor": r["lvFactor"],
                "mtp": r["mtp"],
                "LV": r["LV"],
                "chance": r["chance"],
                "value": r["value"],
                "cost": r["cost"],
                "geneSlot": r["geneSlot"],
                "sort": r["sort"],
                "target": r["target"],
                "proc": r["proc"],
                "type": r["type"],
                "category": r["category"],
                "categorySub": r["categorySub"],
                "abilityType": r["abilityType"],
                "tag": r["tag"],
                "thing": r["thing"],
                "eleP": r["eleP"],
                "max": r["max"],
                "req": r["req"],
                "idTrainer": r["idTrainer"],
                "detail_jp": r["detail_JP"],
                "detail_en": r["detail"],
            }
        )
    return out
