"""官方语言包 XLSX → JSON 导出（纯标准库，共享字符串按 si 聚合 + 列坐标回填）。"""

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .errors import ElinToolError, ExitCode


class LanguageError(ElinToolError):
    """语言包读取或转换失败。"""

    exit_code = ExitCode.GAME_INCOMPLETE


def load_shared_strings(z: zipfile.ZipFile) -> list[str]:
    """共享字符串必须按 <si> 聚合：富文本 <si> 含多个 <r><t> 段，按 <t> 抓会让后续索引整体错位。"""
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return [
        "".join(t.text or "" for t in si.iter("{%s}t" % ns["m"]))
        for si in root.findall("m:si", ns)
    ]


def load_xlsx(path: Path) -> list[list[str]]:
    """读取 sheet1 全部行；23.351 起导出省略空单元格，必须按 r="C3" 列坐标回填。"""
    with zipfile.ZipFile(path) as z:
        strs = load_shared_strings(z)
        sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8", "ignore")
    rows = []
    for r in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        vals = []
        pos = 0
        for m in re.finditer(r"<c\b([^>]*?)(?:/>|>(.*?)</c>)", r, re.S):
            attrs, inner = m.group(1), m.group(2)
            cm = re.search(r'\br="([A-Z]+)\d+"', attrs)
            if cm:
                idx = 0
                for ch in cm.group(1):
                    idx = idx * 26 + ord(ch) - 64
                idx -= 1
            else:
                idx = pos
            while len(vals) <= idx:
                vals.append("")
            vm = re.search(r"<v>(.*?)</v>", inner or "")
            if vm:
                v = vm.group(1)
                vals[idx] = strs[int(v)] if 't="s"' in attrs else v
            pos = idx + 1
        rows.append(vals)
    return rows


def convert(path: Path) -> dict:
    """单个 xlsx → {行id: {列名: 值}}，首行是表头，首列为行 id。"""
    rows = load_xlsx(path)
    if not rows:
        return {}
    hdr = rows[0]
    return {vals[0]: dict(zip(hdr, vals)) for vals in rows[1:] if vals and vals[0]}


def export_lang(src: Path, outdir: Path) -> dict[str, int]:
    """导出语言包目录（递归）下全部 xlsx 到 outdir/<名>.json，任何单文件失败即抛错。"""
    if src.is_dir():
        files = sorted(src.rglob("*.xlsx"))
    elif src.is_file():
        files = [src]
    else:
        raise LanguageError(f"语言包路径不存在：{src}")
    if not files:
        raise LanguageError(f"语言包目录里没有 xlsx：{src}")
    outdir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for f in files:
        try:
            table = convert(f)
        except Exception as e:
            raise LanguageError(f"{f.name}: 转换失败：{e}") from e
        out = outdir / (f.stem + ".json")
        out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
        counts[f.name] = len(table)
    return counts
