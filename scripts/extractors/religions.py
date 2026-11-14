"""SourceReligion strict row parser."""

from ..binary import BinaryCursor

from ..binary import ParseError

def parse_religion_row(c: BinaryCursor) -> dict:
    """按 SourceReligion.Row 的序列化声明顺序读取一行。"""
    row = {
        "_index": c.int(),
        "id": c.string(),
        "name_JP": c.string(),
        "name": c.string(),
        "name2_JP": c.str_array(),
        "name2": c.str_array(),
        "type": c.string(),
        "idMaterial": c.string(),
        "faith": c.string(),
        "domain": c.string(),
        "tax": c.int(),
        "relation": c.int(),
        "elements": c.int_array(),
        "cat_offer": c.str_array(),
        "rewards": c.str_array(),
        "textType_JP": c.string(),
        "textType": c.string(),
        "textAvatar": c.string(),
        "detail_JP": c.string(),
        "detail": c.string(),
        "textBenefit_JP": c.string(),
        "textBenefit": c.string(),
        "textPet_JP": c.string(),
        "textPet": c.string(),
    }
    if not row["id"]:
        raise ParseError("SourceReligion id 不能为空", c.p)
    return row
