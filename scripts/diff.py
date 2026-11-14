"""diff 核心：源码按类型归属的 unified diff 与语言包表/实体对比。"""

import difflib
import json
import re
from collections import defaultdict
from pathlib import Path

from .errors import GameIncompleteError, WorkspaceError

# 外层类型声明行（缩进 0 的 public/internal/abstract/... class|struct|interface|enum）
TYPE_RE = re.compile(
    r"^(?:\[[^\]]*\]\s*)?"
    r"(?:public|internal|private|protected|abstract|sealed|static|partial|unsafe|readonly|ref)"
    r"[\w\s<>,\.\[\]]*?\b(class|struct|interface|enum|record)\s+([A-Za-z_]\w*)"
)
HUNK_HEAD_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
CONTEXT = 3
SAMPLE_CAP = 12
VALID_CHANNELS = ("stable", "nightly")


def load_workspace(ws: Path) -> dict:
    """读取并校验 version.json（dict、channel、version），失败转 WorkspaceError。"""
    vj = ws / "version.json"
    if not ws.is_dir() or not vj.is_file():
        raise WorkspaceError(f"不是有效工作区（缺 version.json）：{ws}")
    try:
        info = json.loads(vj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise WorkspaceError(f"version.json JSON 损坏 {vj}：{e}") from e
    except OSError as e:
        raise WorkspaceError(f"读取 version.json 失败 {vj}：{e}") from e
    if not isinstance(info, dict):
        raise WorkspaceError(f"version.json 顶层必须是 JSON 对象：{vj}")
    if info.get("channel") not in VALID_CHANNELS:
        raise WorkspaceError(
            f"version.json 的 channel 必须是 {' 或 '.join(VALID_CHANNELS)}：{vj}"
            f"（得到 {info.get('channel')!r}）"
        )
    version = info.get("version")
    if not isinstance(version, str) or not version:
        raise WorkspaceError(f"version.json 的 version 必须是非空字符串：{vj}")
    return info


def _scan_type_ranges(lines: list[str]) -> list[tuple[int, int, str]]:
    """扫描缩进 0 的类型声明，返回 [(起始行, 结束行, 全名)]，1-based 闭区间。"""
    decls = []
    ns = None
    for i, line in enumerate(lines, 1):
        if line.startswith("namespace "):
            ns = line.strip().rstrip("{").rstrip(";").strip()[len("namespace ") :].strip()
        elif line.startswith("}"):
            ns = None
        m = TYPE_RE.match(line)
        if m:
            name = f"{ns}.{m.group(2)}" if ns else m.group(2)
            decls.append((i, name))
    ranges = []
    for idx, (start, name) in enumerate(decls):
        end = decls[idx + 1][0] - 1 if idx + 1 < len(decls) else len(lines)
        ranges.append((start, end, name))
    return ranges


def _class_at(ranges: list, lineno: int) -> str:
    """行号所属类型；首个声明之前归 <文件顶层>。"""
    for start, end, name in ranges:
        if start <= lineno <= end:
            return name
    return "<文件顶层>"


def _build_hunks(old_lines: list[str], new_lines: list[str], ops: list) -> list:
    """由 opcodes 构建带上下文的 unified hunk，返回 [(头, [diff 行])]。"""
    blocks = [[a1, a2, b1, b2] for tag, a1, a2, b1, b2 in ops if tag != "equal"]
    merged = []
    for blk in blocks:
        if merged and blk[0] - merged[-1][1] <= 2 * CONTEXT:
            merged[-1][1] = blk[1]
            merged[-1][3] = blk[3]
        else:
            merged.append(blk)
    hunks = []
    for a1, a2, b1, b2 in merged:
        lo = max(0, a1 - CONTEXT)
        hi = min(len(old_lines), a2 + CONTEXT)
        b_lo = b1 - (a1 - lo)
        b_hi = b2 + (hi - a2)
        out = [f"@@ -{lo + 1},{hi - lo} +{b_lo + 1},{b_hi - b_lo} @@"]
        for tag, sa1, sa2, sb1, sb2 in ops:
            zero_width = sa1 == sa2
            if zero_width:
                if sa1 < lo or sa1 > hi:
                    continue
            elif sa2 <= lo or sa1 >= hi:
                continue
            if tag == "equal":
                for k in range(max(sa1, lo), min(sa2, hi)):
                    out.append(" " + old_lines[k])
            elif tag == "replace":
                for k in range(sa1, sa2):
                    out.append("-" + old_lines[k])
                for k in range(sb1, sb2):
                    out.append("+" + new_lines[k])
            elif tag == "delete":
                for k in range(sa1, sa2):
                    out.append("-" + old_lines[k])
            else:
                for k in range(sb1, sb2):
                    out.append("+" + new_lines[k])
        hunks.append((out[0], out[1:]))
    return hunks

def _read_lines(path: Path) -> list[str]:
    """读取源码文件按行拆分，OSError 或非 UTF-8 都转 WorkspaceError。"""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as e:
        raise WorkspaceError(f"源码不是有效 UTF-8（先执行 decompile 转码）：{path}：{e}") from e
    except OSError as e:
        raise WorkspaceError(f"读取源码失败 {path}：{e}") from e


def diff_code(old_ws: Path, new_ws: Path) -> str:
    """对比两个工作区的 src 源码树：新增行按新文件行号归属、删除行按旧文件行号归属。"""
    old_info, new_info = load_workspace(old_ws), load_workspace(new_ws)
    old_src, new_src = old_ws / "src", new_ws / "src"
    for d, ws in ((old_src, old_ws), (new_src, new_ws)):
        if not d.is_dir():
            raise WorkspaceError(f"缺 src 目录（先执行 decompile）：{ws}")
    try:
        old_files = {p.relative_to(old_src).as_posix() for p in old_src.rglob("*.cs")}
        new_files = {p.relative_to(new_src).as_posix() for p in new_src.rglob("*.cs")}
    except OSError as e:
        raise WorkspaceError(f"遍历 src 失败：{e}") from e
    if not old_files and not new_files:
        raise WorkspaceError(
            "两个 workspace 都没有 .cs 源码（先分别执行 decompile），不能据此判断版本无差异"
        )

    stats = defaultdict(lambda: {"+": 0, "-": 0, "samples": []})
    added = removed = changed = 0
    for rel in sorted(old_files | new_files):
        old_p, new_p = old_src / rel, new_src / rel
        if not old_p.is_file():
            added += 1
            old_lines, new_lines = [], _read_lines(new_p)
        elif not new_p.is_file():
            removed += 1
            old_lines, new_lines = _read_lines(old_p), []
        else:
            old_lines = _read_lines(old_p)
            new_lines = _read_lines(new_p)
            if old_lines == new_lines:
                continue
            changed += 1
        ops = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes()
        if all(tag == "equal" for tag, *_ in ops):
            continue
        old_ranges = _scan_type_ranges(old_lines)
        new_ranges = _scan_type_ranges(new_lines)
        for header, lines in _build_hunks(old_lines, new_lines, ops):
            m = HUNK_HEAD_RE.match(header)
            old_n, new_n = int(m.group(1)), int(m.group(2))
            for ln in lines:
                if ln.startswith(" "):
                    old_n += 1
                    new_n += 1
                elif ln.startswith("-"):
                    cls = _class_at(old_ranges, old_n)
                    stats[cls]["-"] += 1
                    if len(stats[cls]["samples"]) < SAMPLE_CAP:
                        stats[cls]["samples"].append((rel, header, ln))
                    old_n += 1
                elif ln.startswith("+"):
                    cls = _class_at(new_ranges, new_n)
                    stats[cls]["+"] += 1
                    if len(stats[cls]["samples"]) < SAMPLE_CAP:
                        stats[cls]["samples"].append((rel, header, ln))
                    new_n += 1

    out = [
        f"旧 workspace: {old_ws}  (channel={old_info.get('channel')} "
        f"version={old_info.get('version')})",
        f"新 workspace: {new_ws}  (channel={new_info.get('channel')} "
        f"version={new_info.get('version')})",
        f"源码文件: 旧 {len(old_files)} / 新 {len(new_files)}；"
        f"新增 {added}，删除 {removed}，修改 {changed}",
    ]
    ranked = sorted(stats.items(), key=lambda kv: -(kv[1]["+"] + kv[1]["-"]))
    if not ranked:
        out.append("两版源码无差异")
        return "\n".join(out)
    out.append(f"共 {len(ranked)} 个类型有改动（按改动量排序）")
    out.append("")
    for name, s in ranked:
        out.append(f"--- {name}   +{s['+']} -{s['-']}")
        last = None
        for rel, header, ln in s["samples"]:
            if (rel, header) != last:
                out.append(f"   {rel} {header}")
                last = (rel, header)
            out.append("     " + ln)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _flat(row: dict) -> dict:
    """比较语义：空字符串与 None 视为无值（沿用旧脚本）。"""
    return {k: v for k, v in row.items() if v not in ("", None)}


def _load_table(path: Path) -> dict:
    """读取语言包 JSON（顶层与行都必须是对象），失败转 GameIncompleteError。"""
    try:
        table = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise GameIncompleteError(f"读取语言包失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise GameIncompleteError(f"语言包 JSON 损坏 {path}：{e}") from e
    if not isinstance(table, dict):
        raise GameIncompleteError(f"语言包 JSON 顶层必须是对象：{path}")
    for k, row in table.items():
        if not isinstance(row, dict):
            raise GameIncompleteError(f"语言包 {path.name} 的行 {k!r} 不是对象")
    return table


def diff_lang(old_ws: Path, new_ws: Path) -> str:
    """对比两个工作区的 data/lang：按表文件与实体 ID 报告新增/删除/修改。"""
    old_info, new_info = load_workspace(old_ws), load_workspace(new_ws)
    old_dir, new_dir = old_ws / "data" / "lang", new_ws / "data" / "lang"
    for d, ws in ((old_dir, old_ws), (new_dir, new_ws)):
        if not d.is_dir():
            raise GameIncompleteError(f"缺 data/lang（先执行 data extract --table lang）：{ws}")

    try:
        names = sorted(
            {p.name for p in old_dir.iterdir()} | {p.name for p in new_dir.iterdir()}
        )
    except OSError as e:
        raise GameIncompleteError(f"遍历 data/lang 失败：{e}") from e
    out = [
        f"旧 workspace: {old_ws}  (channel={old_info.get('channel')} "
        f"version={old_info.get('version')})",
        f"新 workspace: {new_ws}  (channel={new_info.get('channel')} "
        f"version={new_info.get('version')})",
    ]
    tables_added = tables_removed = total_add = total_del = total_mod = 0
    for name in names:
        if not name.endswith(".json"):
            continue
        op, np_ = old_dir / name, new_dir / name
        if not op.is_file():
            tables_added += 1
            out.append(f"[新增表] {name}")
            continue
        if not np_.is_file():
            tables_removed += 1
            out.append(f"[删除表] {name}")
            continue
        old, new = _load_table(op), _load_table(np_)
        added = [k for k in new if k not in old]
        removed_keys = [k for k in old if k not in new]
        modified = [k for k in old if k in new and _flat(old[k]) != _flat(new[k])]
        if not (added or removed_keys or modified):
            continue
        out.append(f"=== {name}  +{len(added)} -{len(removed_keys)} ~{len(modified)} ===")
        for k in added:
            row = new[k]
            label = row.get("name") or row.get("text") or ""
            extra = {c: v for c, v in row.items() if c != "name" and v not in ("", None)}
            out.append(f"  [+] {k}  {label}  {json.dumps(extra, ensure_ascii=False)[:220]}")
        for k in removed_keys:
            row = old[k]
            label = row.get("name") or row.get("text") or ""
            out.append(f"  [-] {k}  {label}")
        for k in modified:
            o, n = _flat(old[k]), _flat(new[k])
            for c in sorted(set(o) | set(n)):
                if o.get(c, "") == n.get(c, ""):
                    continue
                ov, nv = str(o.get(c, "")), str(n.get(c, ""))
                if len(ov) > 60:
                    ov = ov[:60] + "…"
                if len(nv) > 60:
                    nv = nv[:60] + "…"
                out.append(f"  [~] {k}.{c}: {ov}  ->  {nv}")
        total_add += len(added)
        total_del += len(removed_keys)
        total_mod += len(modified)
    out.append(
        f"合计: +{total_add} -{total_del} ~{total_mod}；"
        f"表级: 新增 {tables_added} 张，删除 {tables_removed} 张"
    )
    if not (total_add or total_del or total_mod or tables_added or tables_removed):
        out.append("两版语言包无差异")
    return "\n".join(out) + "\n"
