"""SourceChara / SourceRace / SourceJob 严格行解析。"""

from ..binary import BinaryCursor


def parse_chara_row(c: BinaryCursor) -> dict:
    """CardRow → RenderRow 前缀 + CardRow 字段 + 角色专属尾部，声明序解析。"""
    row = {"_index": c.int()}
    row["tiles"] = c.int_array(256)
    row["_tiles"] = c.int_array(256)
    row["skins"] = c.int_array(256)
    for k in ("colorMod", "sort", "value", "LV", "chance", "tempChance", "snowTile"):
        row[k] = c.int()
    row["name"] = c.string()
    row["name_JP"] = c.string()
    row["detail"] = c.string()
    row["detail_JP"] = c.string()
    row["_idRenderData"] = c.string()
    row["_tileType"] = c.string()
    row["defMat"] = c.string()
    row["colorType"] = c.string()
    row["category"] = c.string()
    row["idSound"] = c.string()
    row["aliasPref"] = c.string()
    row["components"] = c.str_array(64)
    row["factory"] = c.str_array(64)
    row["recipeKey"] = c.str_array(64)
    row["tag"] = c.str_array(64)
    row["W"] = c.int()
    row["H"] = c.int()
    row["multisize"] = c.boolean()
    row["fixedMaterial"] = c.boolean()
    row["pref_ints"] = c.int_array(64)
    row["id"] = c.string()
    row["idExtra"] = c.string()
    row["tierGroup"] = c.string()
    row["lightData"] = c.string()
    row["_origin"] = c.string()
    row["idShadow"] = c.int()
    row["quality"] = c.int()
    row["elements"] = c.int_array(256)
    row["shadow"] = c.int_array(64)
    row["size"] = c.int_array(64)
    row["light"] = c.int_array(64)
    row["loot"] = c.str_array(64)
    row["filter"] = c.str_array(64)
    row["trait"] = c.str_array(64)
    row["idActor"] = c.str_array(64)
    row["vals"] = c.str_array(64)
    row["name2"] = c.str_array(64)
    row["name2_JP"] = c.str_array(64)
    row["_id"] = c.int()
    row["aka_JP"] = c.string()
    row["aka"] = c.string()
    row["tiles_snow"] = c.int_array(256)
    row["hostility"] = c.string()
    row["biome"] = c.string()
    row["race"] = c.string()
    row["job"] = c.string()
    row["tactics"] = c.string()
    row["aiIdle"] = c.string()
    row["aiParam"] = c.int_array(64)
    row["actCombat"] = c.str_array(64)
    row["mainElement"] = c.str_array(64)
    row["equip"] = c.string()
    row["gachaFilter"] = c.str_array(64)
    row["tone"] = c.string()
    row["actIdle"] = c.str_array(64)
    row["bio"] = c.string()
    row["faith"] = c.string()
    row["works"] = c.str_array(64)
    row["hobbies"] = c.str_array(64)
    row["idText"] = c.string()
    row["moveAnime"] = c.string()
    row["recruitItems"] = c.str_array(64)
    row["staticSkin"] = c.boolean()
    row["_tiles_snow"] = c.int_array(256)
    row["skinAntiSpider"] = c.int()
    return row


RACE_STATS = (
    "life",
    "mana",
    "vigor",
    "DV",
    "PV",
    "PDR",
    "EDR",
    "EP",
    "STR",
    "END",
    "DEX",
    "PER",
    "LER",
    "WIL",
    "MAG",
    "CHA",
    "SPD",
    "INT",
    "martial",
    "pen",
)


def parse_race_row(c: BinaryCursor) -> dict:
    """SourceRace.Row 声明序解析。"""
    row = {"_index": c.int()}
    row["id"] = c.string()
    row["name_JP"] = c.string()
    row["name"] = c.string()
    row["playable"] = c.int()
    row["tag"] = c.str_array(64)
    for k in RACE_STATS:
        row[k] = c.int()
    row["elements"] = c.int_array(256)
    row["skill"] = c.string()
    row["figure"] = c.string()
    row["geneCap"] = c.int()
    row["material"] = c.string()
    row["corpse"] = c.str_array(64)
    row["loot"] = c.str_array(64)
    row["blood"] = c.int()
    row["meleeStyle"] = c.string()
    row["castStyle"] = c.string()
    row["EQ"] = c.str_array(64)
    row["sex"] = c.int()
    row["age"] = c.int_array(64)
    row["height"] = c.int()
    row["breeder"] = c.int()
    row["food"] = c.str_array(64)
    row["fur"] = c.string()
    row["detail_JP"] = c.string()
    row["detail"] = c.string()
    return row


def parse_job_row(c: BinaryCursor) -> dict:
    """SourceJob.Row 声明序解析。"""
    row = {"_index": c.int()}
    row["id"] = c.string()
    row["name_JP"] = c.string()
    row["name"] = c.string()
    row["playable"] = c.int()
    for k in ("STR", "END", "DEX", "PER", "LER", "WIL", "MAG", "CHA", "SPD"):
        row[k] = c.int()
    row["elements"] = c.int_array(256)
    row["weapon"] = c.str_array(64)
    row["equip"] = c.string()
    row["domain"] = c.int_array(256)
    row["detail_JP"] = c.string()
    row["detail"] = c.string()
    return row
