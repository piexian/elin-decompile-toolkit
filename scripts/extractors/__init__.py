"""表注册表：--table 名称 → 提取函数、输出文件与语言包校验配置。"""

from . import charas, elements, materials, things, zones
from .core import extract_table
from . import religions as religions

TABLES = {
    "things": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceThing", things.parse_thing_row, (1000, 6000)
        )[0],
        "out": "things_full.jsonl",
        "jsonl": True,
        "lang": "Thing.json",
        "ids": "equal",
    },
    "categories": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceCategory", things.parse_category_row, (50, 600)
        )[0],
        "out": "categories.json",
        "jsonl": False,
        "lang": "Category.json",
        "ids": "equal",
        "allow": {""},
    },
    "spawnlists": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceSpawnList", things.parse_spawnlist_row, (5, 600)
        )[0],
        "out": "spawnlists.json",
        "jsonl": False,
        "lang": "SpawnList.json",
        "ids": "equal",
    },
    "materials": {
        "extract": lambda data, lang_dir: materials.extract(data),
        "out": "materials.jsonl",
        "jsonl": True,
        "lang": "Material.json",
        "ids": "equal",
        "numeric": True,
        "lang_build": materials.build_outputs,
    },
    "elements": {
        "extract": lambda data, lang_dir: elements.extract(data),
        "out": "elements.jsonl",
        "jsonl": True,
        "lang": "Element.json",
        "ids": "equal",
        "id_column": True,
        "allow": elements.RUNTIME_IDS,
        "row_build": elements.build_outputs,
    },
    "charas": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceChara", charas.parse_chara_row, (100, 5000)
        )[0],
        "out": "charas_full.jsonl",
        "jsonl": True,
        "lang": "Chara.json",
        "ids": "equal",
    },
    "races": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceRace", charas.parse_race_row, (20, 600)
        )[0],
        "out": "races.json",
        "jsonl": False,
        "lang": "Race.json",
        "ids": "equal",
    },
    "jobs": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceJob", charas.parse_job_row, (10, 300)
        )[0],
        "out": "jobs.json",
        "jsonl": False,
        "lang": "Job.json",
        "ids": "equal",
    },
    "zones": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceZone", zones.parse_zone_row, (80, 200)
        )[0],
        "out": "zones_full.json",
        "jsonl": False,
        "lang": "Zone.json",
        "ids": "equal",
    },
    "quests": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceQuest", zones.parse_quest_row, (100, 400)
        )[0],
        "out": "quests_full.json",
        "jsonl": False,
        "lang": "Quest.json",
        "ids": "equal",
    },
    "religions": {
        "extract": lambda data, lang_dir: extract_table(
            data, "SourceReligion", religions.parse_religion_row, (1, 100)
        )[0],
        "out": "religions.json",
        "jsonl": False,
        "lang": "Religion.json",
        "ids": "equal",
    },
}

TABLE_ORDER = [
    "things",
    "categories",
    "spawnlists",
    "materials",
    "elements",
    "charas",
    "races",
    "jobs",
    "zones",
    "quests",
    "religions",
]
