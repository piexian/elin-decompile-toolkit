"""chunks：把 kb/corpus 打包成 AstrBot WebUI 可直接上传的聚合 .md + MANIFEST.md。

AstrBot 对 .md 走 MarkdownChunker：每个一级标题独立成块，相邻短块不合并。
所以按 SECTION（略小于分块大小）贪心打包段落，再拼成大文件，让段落顶满分块大小。
"""

import json
import re
import shutil
from pathlib import Path

from .errors import ElinToolError, ExitCode, GameIncompleteError, WorkspaceError

# WebUI 的「分块大小」。段落必须比它略小，否则段落会被二次切分。
DEFAULT_SIZE = 2048
SECTION_MARGIN = 80  # 80 字符留给标题行和余量
# 单个上传文件的目标字符数，太大 WebUI 一次处理会很慢
BATCH = 240_000

# 渲染 / UI / 音频 / 网络 / 引擎设置类，与 wiki 词条无关，默认不嵌入。
PRUNE_PREFIX = re.compile(
    r"^(UI|Layer|Render|Mesh|Shader|Sprite|Camera|PostEffect|Refraction|Bloom|"
    r"Audio|Sound|BGM|Net|Steam|Input|Coroutine|Tween|Scene|Effect3D|WebGL|"
    r"Http|Download|Cursor|Scroll|Particle|Weather|Light|Fog|Skybox|Animator|"
    r"Physics|Rigidbody|Collider|Gui)",
    re.I,
)
PRUNE_EXACT = {
    "BaseTileMap", "TileMapElona", "CoreDebug", "ModUtil", "ModManager",
    "DramaManager", "DramaCustomSequence", "Application", "Point", "ColorExt",
    "StringExt", "ListExt", "MathfExt",
}

DATA_FOLDERS = ["items", "charas", "elements", "materials", "categories", "zones"]
FOLDER_CN = {
    "items": "物品",
    "charas": "角色",
    "elements": "元素",
    "materials": "材质",
    "categories": "类别",
    "zones": "地区",
}


class ChunkError(ElinToolError):
    """chunk 打包失败。"""

    exit_code = ExitCode.GAME_INCOMPLETE


def demote_headings(text: str) -> str:
    """把正文里的 markdown 标题降级为粗体，避免在聚合文件里被再切成独立块。"""
    return re.sub(r"^(#{1,4})\s+(.+)$", r"**\2**", text, flags=re.M)


def split_long(text: str, limit: int) -> list[str]:
    """把超长文本按 空行 -> 换行 -> 硬切 的顺序切成 <= limit 的段。"""
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        cand = (cur + "\n\n" + para) if cur else para
        if cur and len(cand) > limit:
            parts.append(cur)
            cur = para
        else:
            cur = cand
    if cur:
        parts.append(cur)
    final = []
    for p in parts:
        while len(p) > limit:
            cut = p.rfind("\n", 0, limit)
            if cut <= 0:
                cut = limit
            final.append(p[:cut])
            p = p[cut:]
        if p.strip():
            final.append(p)
    return final


def make_title(group: str, items: list) -> str:
    """段落标题带上分组名，块脱离上下文时也知道自己在讲哪一类。"""
    first = items[0][0]
    label = f"未归类{group[1:]}" if group.startswith("~") else group
    if len(items) == 1:
        return first
    if first.split("（")[0] == label:
        return f"{label} 等 {len(items)} 项"
    return f"{label}：{first} 等 {len(items)} 项"


def pack(entries: list, section: int) -> list:
    """entries: [(group, title, body)] -> [(title, 合并后的正文)]。
    group 相同的条目尽量排在一起并填进同一段落；跨 group 不混装。"""
    groups = {}
    for group, title, body in entries:
        groups.setdefault(group, []).append((title, body))
    out = []
    for group, items in groups.items():
        cur, cur_len = [], 0
        for title, body in items:
            need = len(title) + 2 + len(body) + 2
            if cur and cur_len + need > section:
                out.append((make_title(group, cur), "\n\n".join(b for _, b in cur)))
                cur, cur_len = [], 0
            cur.append((title, body))
            cur_len += need
        if cur:
            out.append((make_title(group, cur), "\n\n".join(b for _, b in cur)))
    return out


def pack_code(classes: list, section: int) -> list:
    """反编译源码专用：按行流式填段，跨类拼段时插 `// 类: X` 行保留出处。"""
    budget = section - 40
    out, buf, size, first, prev = [], [], 0, None, None

    def flush():
        nonlocal buf, size, first
        if buf:
            text = "".join(buf)
            n = 1 + text.count("// 类: ")
            title = (
                f"Elin 反编译：{first} 等 {n} 类" if n > 1 else f"Elin 反编译：{first}"
            )
            out.append((title, "```csharp\n" + text.rstrip() + "\n```"))
        buf, size, first = [], 0, None

    for cls, fn, body in classes:
        if prev is not None and cls != prev:
            marker = f"// 类: {cls} (Elin 反编译)\n"
            if size + len(marker) > budget:
                flush()
            if first is None:
                first = cls
            buf.append(marker)
            size += len(marker)
        for line in body.split("\n"):
            piece = line + "\n"
            if size + len(piece) > budget:
                flush()
            if first is None:
                first = cls
            buf.append(piece)
            size += len(piece)
        prev = cls
    flush()
    return out


def write_batches(sections: list, prefix: str, out: Path) -> tuple:
    """把段落写成若干 <= BATCH 字符的聚合文件，返回 (文件数, 块数, 字符数)。"""
    out.mkdir(parents=True, exist_ok=True)
    files, chunks, chars, buf = 0, 0, 0, []
    batches = []
    for title, body in sections:
        sec = f"# {title}\n\n{body}"
        if buf and sum(len(x) for x in buf) + len(sec) > BATCH:
            batches.append(buf)
            buf = []
        buf.append(sec)
    if buf:
        batches.append(buf)
    for i, batch in enumerate(batches, 1):
        # 不写文件头注释/散文本：MarkdownChunker 会把首标题前的散文本单独成块
        try:
            (out / f"{prefix}_{i:02d}.md").write_text(
                "\n\n".join(batch).rstrip() + "\n", encoding="utf-8"
            )
        except OSError as e:
            raise ChunkError(f"写出聚合文件失败 {prefix}_{i:02d}.md：{e}") from e
        files += 1
        chunks += len(batch)
        chars += sum(len(x) for x in batch)
    return files, chunks, chars


def load_category_ids(corpus: Path) -> set:
    """类别 id 集合（Category.json 的行 id 与 name_EN）；损坏/缺失明确报错。"""
    p = corpus.parent.parent / "data" / "lang" / "Category.json"
    try:
        rows = json.loads(p.read_text(encoding="utf-8-sig"))
    except OSError as e:
        raise GameIncompleteError(f"读取类别语言表失败 {p}：{e}") from e
    except json.JSONDecodeError as e:
        raise GameIncompleteError(f"类别语言表 JSON 损坏 {p}：{e}") from e
    if not isinstance(rows, dict):
        raise GameIncompleteError(f"类别语言表顶层必须是对象：{p}")
    for k, r in rows.items():
        if not isinstance(r, dict):
            raise GameIncompleteError(f"类别语言表 {p.name} 的行 {k!r} 不是对象")
    ids = {r.get("name_EN", "") for r in rows.values()}
    ids |= set(rows.keys())
    return {i for i in ids if i}


def item_category(text: str, cat_ids: set):
    """从 items 条目的分类行认出类别 token（可能是细分如 obj_S / meal_cookie）。"""
    m = re.search(r"^- 分类: (.+)$", text, re.M)
    if not m:
        return None
    tok = m.group(1).strip()
    if tok in cat_ids:
        return tok
    for cid in cat_ids:
        if tok.startswith(cid + "_"):
            return cid
    return None


def parse_entry(text: str) -> tuple:
    """拆出 (标题, 正文)；标题是第一条一级标题。"""
    text = text.strip()
    m = re.match(r"^#\s+(.+?)\n(.*)$", text, re.S)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return text.split("\n", 1)[0][:60], text


def num_key(s: str):
    m = re.search(r"(\d+)", s)
    return (0, int(m.group(1))) if m else (1, 0)


def build_code(workspace: Path, out: Path, section: int, report: list) -> tuple:
    """反编译类 → code_*.md；读 kb/source/classes（source split 的输出）。"""
    codedir = workspace / "kb" / "source" / "classes"
    if not codedir.is_dir():
        raise ChunkError(
            f"缺 kb/source/classes（先执行 source split 再 --code）：{codedir}"
        )
    classes = []
    skipped_empty = 0
    skipped_pruned = 0
    for fn in sorted(codedir.iterdir()):
        if not fn.name.endswith(".cs"):
            continue
        cls = fn.stem
        if PRUNE_PREFIX.match(cls) or cls in PRUNE_EXACT:
            skipped_pruned += 1
            continue
        try:
            body = fn.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as e:
            raise ChunkError(f"读取代码语料失败 {fn}：{e}") from e
        # 空壳类（只有 class/接口声明和一对花括号）对检索没有价值
        if len(re.sub(r"[\s{}/\[\]():;,]*class[\w\s]*$", "", body, flags=re.M)) < 40:
            skipped_empty += 1
            continue
        classes.append((cls, fn.name, body))
    sections = pack_code(classes, section)
    report.append(("code",) + write_batches(sections, "code", out))
    return skipped_empty, skipped_pruned


def build(workspace: Path, size: int, skip_code: bool = True) -> None:
    """打包 workspace/kb/corpus → workspace/kb/embed_ready + kb/MANIFEST.md。"""
    from .diff import load_workspace

    info = load_workspace(workspace)
    version = info.get("version", "unknown")
    if size <= SECTION_MARGIN:
        raise WorkspaceError(f"--size 太小（至少 {SECTION_MARGIN + 1}）：{size}")
    corpus = workspace / "kb" / "corpus"
    out = workspace / "kb" / "embed_ready"
    manifest_path = workspace / "kb" / "MANIFEST.md"
    if not corpus.is_dir():
        raise GameIncompleteError(f"缺 kb/corpus（先执行 corpus build）：{workspace}")
    if out.is_symlink() or (out.exists() and not out.is_dir()):
        raise GameIncompleteError(
            f"聚合输出路径已存在且不是目录或是指向别处的符号链接，拒绝操作：{out}"
        )
    try:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
    except OSError as e:
        raise ChunkError(f"准备聚合输出目录失败 {out}：{e}") from e
    section = size - SECTION_MARGIN
    cat_ids = load_category_ids(corpus)
    report = []

    # ---- data：实体条目 ----
    entries = []
    for folder in DATA_FOLDERS:
        d = corpus / folder
        if not d.is_dir():
            continue
        for fn in sorted(d.iterdir()):
            if not fn.name.endswith(".md"):
                continue
            try:
                text = fn.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as e:
                raise ChunkError(f"读取语料条目失败 {fn}：{e}") from e
            title, body = parse_entry(text)
            body = demote_headings(body)
            # 打包后段落标题只保留第一个实体，所以每个实体都要在正文里自带
            # 一行自己的名字 + id，否则同段落里后面的实体的 id 和主名就丢了。
            body = f"**{title}**\n{body}"
            if folder == "items":
                group = item_category(text, cat_ids) or f"~{FOLDER_CN[folder]}"
            else:
                group = FOLDER_CN[folder]
            entries.append((group, title, body))
    entries.sort(key=lambda e: (e[0], num_key(e[1])))
    sections = pack(entries, section)
    report.append(("data",) + write_batches(sections, "data", out))

    # ---- doc：versions（版本变动 + 考据知识）----
    entries = []
    base = corpus / "versions"
    if base.is_dir():
        for path in sorted(base.rglob("*")):
            if not path.name.endswith((".md", ".txt")):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as e:
                raise ChunkError(f"读取语料条目失败 {path}：{e}") from e
            name = path.stem.replace("_", " ")
            # 先按二级标题切，再降级标题，保证每个段落只有一个 markdown 标题
            for i, sec in enumerate(re.split(r"\n(?=##\s)", text), 1):
                sec = sec.strip()
                if not sec:
                    continue
                sec = re.sub(r"^##\s+(.+)$", r"# \1", sec, flags=re.M)
                sec = demote_headings(sec)
                parts = split_long(sec, section)
                for j, part in enumerate(parts, 1):
                    seg = f"（第{i}节，共{len(parts)}段）" if len(parts) > 1 else ""
                    entries.append((name, f"{name}{seg}", part))
    entries.sort(key=lambda e: e[0])
    sections = pack(entries, section)
    report.append(("doc",) + write_batches(sections, "doc", out))

    # ---- code：默认停传（检索走 AstrBot 插件直查本地源码），--code 恢复 ----
    skipped_empty = skipped_pruned = 0
    if skip_code:
        report.append(("code", 0, 0, 0))
    else:
        skipped_empty, skipped_pruned = build_code(workspace, out, section, report)

    # ---- 清单 ----
    total_c = sum(r[2] for r in report)
    total_f = sum(r[1] for r in report)
    lines = [
        "# AstrBot 上传清单",
        "",
        f"数据版本 **{version}**（来自工作区 version.json）。上传目录是 `kb/embed_ready/`"
        f"（本清单在上传目录之外，不进知识库）。每个 `# 标题` 段落 = WebUI 的一个文本块，"
        f"共 **{total_f} 个文件 / 约 {total_c} 块**，可以一次全量重建。",
        "",
        "| 文件前缀 | 上传文件数 | 段落数（≈嵌入块数） | 字符数 |",
        "|---|---|---|---|",
    ]
    for group, f_, c_, ch_ in report:
        if f_ == 0:
            continue
        lines.append(f"| `{group}_*.md` | {f_} | {c_} | {ch_:,} |")
    lines += [
        f"| **合计** | **{total_f}** | **{total_c}** | |",
        "",
        "## WebUI 设置",
        "",
        f"- **分块大小设 {size}、分块重叠 100**。语料段落都按 {section} 字符打包，"
        "一个段落正好一个块，不会被二次切分。**切分参数和上传目录是配套的**：改了分块大小就要重跑 "
        f"`scripts chunks --workspace <工作区> --size <新的分块大小>`。",
        f"- 想更快：重跑 `scripts chunks --workspace <工作区> --size 4096`，"
        f"块数约 {total_c // 2}，但单块更大、检索更粗。mistral-embed 支持 8192 token，4096 字符不会超。",
        f"- 块变大后**检索数量要跟着降**：块是 {size} 字符时，"
        f"稠密检索 / 稀疏检索建议设 **15 / 15**（设 50 会一次塞进 "
        f"{50 * size // 1000}K 字符，上下文又慢又稀释）。",
        "",
        "## 剔除内容",
        "",
    ]
    if skip_code:
        lines += [
            "- **代码语料停传**：源码检索走 AstrBot 插件 `astrbot_plugin_self_file_search` "
            "直查本地拆分源码，嵌入库只放译名对照与数据语料。要恢复传代码加 `--code`。",
        ]
    else:
        lines += [
            f"- 渲染 / UI / 音频 / 网络 / 引擎设置类 **{skipped_pruned} 个**"
            "（PRUNE_PREFIX / PRUNE_EXACT，设成空即可全量嵌入）。",
            f"- 空壳类（只有类声明没有实现）**{skipped_empty} 个**。",
        ]
    # 清单是给人看的操作说明，不进上传目录——上传目录里只能有语料本体
    if manifest_path.is_symlink() or (
        manifest_path.exists() and not manifest_path.is_file()
    ):
        raise ChunkError(
            f"清单路径已是指向别处的符号链接或非普通文件，拒绝写入：{manifest_path}"
        )
    try:
        manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        raise ChunkError(f"写出清单失败 {manifest_path}：{e}") from e

    for group, f_, c_, ch_ in report:
        if f_ or c_:
            print(f"{group}: {f_} 个聚合文件 -> {c_} 块, {ch_:,} 字符")
    print(f"合计 {total_c} 块 / {total_f} 个文件")
    if skip_code:
        print("代码语料已跳过（--code 恢复）")
    print(f"WebUI 分块大小请设 {size}")
    print(f"输出: {out}")
    print(f"清单: {manifest_path}")
