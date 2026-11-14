"""Ylvapedia wikitext readers for optional, source-stamped page enrichment."""

import re

from .errors import ElinToolError, ExitCode


class WikitextError(ElinToolError):
    """Wikitext structure is not supported or incomplete."""

    exit_code = ExitCode.GAME_INCOMPLETE


def table_cells(line: str) -> list[str]:
    """Split one wikitable row into raw cell strings."""
    line = line.strip()
    if line.startswith("|-"):
        line = line[2:].strip()
    if not line.startswith("|"):
        return []
    return [cell.strip() for cell in line.lstrip("|").split("|")]


def wiki_link_id(text: str) -> str:
    """Return a Bestiary page's final path component as a link id."""
    match = re.search(r"\[\[Elin:Bestiary/([^\]|]+)", text)
    if not match:
        return ""
    return match.group(1).rsplit("/", 1)[-1].strip()


def unique_npcs(wikitext: str) -> list[dict]:
    """解析 Unique NPC 表；该页把每个单元格写成独立 wikitext 行。"""
    header = ("Name", "Level", "Race", "Class", "Animosity", "Spells/Abilities", "Feats", "AI", "Notes")
    result = []
    cells = []
    in_table = False
    for line in wikitext.splitlines() + ["|-"]:
        if line.startswith("{|"):
            in_table = True
            cells = []
            continue
        if not in_table:
            continue
        if line.startswith("!"):
            continue
        if line.startswith("|}"):
            break
        if line.startswith("|-"):
            if len(cells) == len(header):
                item = dict(zip(header, cells))
                item["link_id"] = wiki_link_id(cells[0])
                if item["link_id"]:
                    result.append(item)
            cells = []
            continue
        if line.startswith("|"):
            content = line[1:].strip()
            if content.startswith("colspan"):
                continue
            cells.append(content)
    return result


def infobox(wikitext: str) -> dict:
    """Read simple Infobox Profile keys from a single god/NPC page."""
    match = re.search(r"\{\{Infobox Profile(.*?)\n\}\}", wikitext, re.S)
    if not match:
        raise WikitextError("页面没有 Infobox Profile")
    result = {}
    for line in match.group(1).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip().lstrip("|").strip()] = value.strip()
    return result
