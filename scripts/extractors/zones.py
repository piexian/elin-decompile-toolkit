"""SourceZone / SourceQuest 严格行解析（name_L/detail_L 等运行时扩展列不在流里）。"""

from ..binary import BinaryCursor


def parse_zone_row(c: BinaryCursor) -> dict:
    """SourceZone.Row 声明序解析。"""
    row = {"_index": c.int()}
    row["id"] = c.string()
    row["parent"] = c.string()
    row["name_JP"] = c.string()
    row["name"] = c.string()
    row["type"] = c.string()
    row["LV"] = c.int()
    row["chance"] = c.int()
    row["faction"] = c.string()
    row["value"] = c.int()
    row["idProfile"] = c.string()
    row["idFile"] = c.str_array(64)
    row["idBiome"] = c.string()
    row["idGen"] = c.string()
    row["idPlaylist"] = c.string()
    row["tag"] = c.str_array(64)
    row["costSkyTravel"] = c.int()
    row["cost"] = c.int()
    row["dev"] = c.int()
    row["image"] = c.string()
    row["pos"] = c.int_array(64)
    row["questTag"] = c.str_array(64)
    row["textFlavor_JP"] = c.string()
    row["textFlavor"] = c.string()
    row["detail_JP"] = c.string()
    row["detail"] = c.string()
    return row


def parse_quest_row(c: BinaryCursor) -> dict:
    """SourceQuest.Row 声明序解析。"""
    row = {"_index": c.int()}
    row["id"] = c.string()
    row["name_JP"] = c.string()
    row["name"] = c.string()
    row["type"] = c.string()
    row["drama"] = c.str_array(64)
    row["idZone"] = c.string()
    row["group"] = c.string()
    row["tags"] = c.str_array(64)
    row["money"] = c.int()
    row["chance"] = c.int()
    row["minFame"] = c.int()
    row["detail_JP"] = c.string()
    row["detail"] = c.string()
    row["talkProgress_JP"] = c.string()
    row["talkProgress"] = c.string()
    row["talkComplete_JP"] = c.string()
    row["talkComplete"] = c.string()
    return row
