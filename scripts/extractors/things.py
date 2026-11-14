"""SourceThing / SourceCategory / SourceSpawnList 严格行解析与 canonical 生成。"""

from ..binary import BinaryCursor

THING_INTS_HEAD = ["colorMod", "sort", "value", "LV", "chance", "tempChance", "snowTile"]


def parse_thing_row(c: BinaryCursor) -> dict:
    """RenderRow + CardRow + SourceThing.Row 声明序解析（colorType 声明存在但不在流里）。"""
    row = {"_index": c.int()}
    row["tiles"] = c.int_array(256)
    row["_tiles"] = c.int_array(256)
    row["skins"] = c.int_array(256)
    for k in THING_INTS_HEAD:
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
    row["pref_ints"] = c.int_array(256)
    row["id"] = c.string()
    row["idExtra"] = c.string()
    row["tierGroup"] = c.string()
    row["lightData"] = c.string()
    row["_origin"] = c.string()
    row["idShadow"] = c.int()
    row["quality"] = c.int()
    row["elements"] = c.int_array(256)
    row["shadow"] = c.int_array(256)
    row["size"] = c.int_array(256)
    row["light"] = c.int_array(256)
    row["loot"] = c.str_array(64)
    row["filter"] = c.str_array(64)
    row["trait"] = c.str_array(64)
    row["idActor"] = c.str_array(64)
    row["vals"] = c.str_array(64)
    row["name2"] = c.str_array(64)
    row["name2_JP"] = c.str_array(64)
    row["unknown_JP"] = c.string()
    row["unit_JP"] = c.string()
    row["naming"] = c.string()
    row["unit"] = c.string()
    row["unknown"] = c.string()
    row["altTiles"] = c.int_array(256)
    row["anime"] = c.int_array(256)
    row["disassemble"] = c.str_array(64)
    row["HP"] = c.int()
    row["weight"] = c.int()
    row["electricity"] = c.int()
    row["range"] = c.int()
    row["attackType"] = c.string()
    row["offense"] = c.int_array(256)
    row["substats"] = c.int_array(256)
    row["defense"] = c.int_array(256)
    row["idToggleExtra"] = c.string()
    row["idActorEx"] = c.string()
    row["workTag"] = c.string()
    row["roomName_JP"] = c.str_array(64)
    row["roomName"] = c.str_array(64)
    row["_altTiles"] = c.int_array(256)
    row["ignoreAltFix"] = c.boolean()
    row["animeNoSync"] = c.boolean()
    return row


def parse_category_row(c: BinaryCursor) -> dict:
    """SourceCategory.Row 声明序解析。"""
    row = {"_index": c.int()}
    row["id"] = c.string()
    row["uid"] = c.int()
    row["name_JP"] = c.string()
    row["name"] = c.string()
    row["_parent"] = c.string()
    row["recipeCat"] = c.string()
    row["slot"] = c.int()
    row["skill"] = c.int()
    row["maxStack"] = c.int()
    row["tileDummy"] = c.int()
    row["installOne"] = c.boolean()
    row["ignoreBless"] = c.int()
    row["tag"] = c.str_array(64)
    row["idThing"] = c.string()
    row["recycle"] = c.str_array(64)
    row["costSP"] = c.int()
    row["gift"] = c.int()
    row["deliver"] = c.int()
    row["offer"] = c.int()
    row["ticket"] = c.int()
    row["sortVal"] = c.int()
    row["flag"] = c.int()
    return row


def parse_spawnlist_row(c: BinaryCursor) -> dict:
    """SourceSpawnList.Row 声明序解析。"""
    row = {"_index": c.int()}
    row["id"] = c.string()
    row["parent"] = c.string()
    row["type"] = c.string()
    row["category"] = c.str_array(64)
    row["idCard"] = c.str_array(64)
    row["tag"] = c.str_array(64)
    row["filter"] = c.str_array(64)
    return row


def build_canonical(thing_rows: list) -> tuple[list, list]:
    """从严格 SourceThing 行生成 canonical things 与 recipes，固定字段布局。"""
    things = []
    recipes = []
    for r in thing_rows:
        things.append(
            {
                "id": r["id"],
                "name_en": r["name"],
                "name_jp": r["name_JP"],
                "category": r["category"],
                "defMat": r["defMat"],
                "recipe_key": r["recipeKey"],
                "components": r["components"],
                "factory": r["factory"],
                "extra": r["idExtra"],
                "traits": r["trait"],
                "filters": r["filter"],
            }
        )
        if r["components"] and r["components"] != ["-"] and r["factory"]:
            recipes.append(
                {
                    "id": r["id"],
                    "name_en": r["name"],
                    "name_jp": r["name_JP"],
                    "recipe_key": r["recipeKey"],
                    "components": r["components"],
                    "factory": r["factory"],
                }
            )
    return things, recipes
