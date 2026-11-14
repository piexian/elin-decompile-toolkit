"""source split：把反编译源码按类型拆成单文件（兼容单文件与项目目录两种输入）。

单文件模式（默认输入 workspace/src/Elin.decompiled.cs）：大括号深度追踪、嵌套类型
独立成文件、父类嵌套位置写占位注释、同名类型加 _1 后缀。
项目目录模式：递归收集 .cs，逐文件 UTF-8 校验后复制到 classes，重名加后缀。
"""

import re
from pathlib import Path

from .errors import ElinToolError, ExitCode, WorkspaceError

DEFAULT_INPUT = "src/Elin.decompiled.cs"
DEFAULT_OUTPUT = "kb/source/classes"

DECL = re.compile(
    r"^([ \t]*)((?:public|internal|private|protected)\s+)*(?:abstract\s+|static\s+|sealed\s+|partial\s+|readonly\s+|unsafe\s+|new\s+)*(class|enum|interface|struct)\s+([A-Za-z_0-9]+)"
)


class SourceError(ElinToolError):
    """源码拆分失败。"""

    exit_code = ExitCode.GAME_INCOMPLETE


def _read_utf8(path: Path) -> str:
    """严格 UTF-8 读取，失败转 SourceError。"""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise SourceError(f"读取源码失败 {path}：{e}") from e
    except UnicodeDecodeError as e:
        raise SourceError(f"源码不是有效 UTF-8（先执行 decompile 转码）：{path}：{e}") from e


def _prepare_outdir(outdir: Path, workspace: Path) -> None:
    """输出目录及其 workspace 内父链是 symlink/非目录拒绝；先安全清理旧 .cs。"""
    cur = outdir
    while cur != workspace and workspace in cur.parents:
        if cur.is_symlink() or (cur.exists() and not cur.is_dir()):
            raise WorkspaceError(
                f"输出路径已存在且不是目录或是指向别处的符号链接，拒绝操作：{cur}"
            )
        cur = cur.parent
    if outdir.is_symlink() or (outdir.exists() and not outdir.is_dir()):
        raise WorkspaceError(
            f"输出路径已存在且不是目录或是指向别处的符号链接，拒绝操作：{outdir}"
        )
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        for f in sorted(outdir.iterdir()):
            if f.suffix == ".cs":
                f.unlink()
    except OSError as e:
        raise SourceError(f"准备输出目录失败 {outdir}：{e}") from e


def split_file(text: str) -> list:
    """大括号深度追踪拆类型：返回 [(类型名, 正文行列表)]，父类挖掉嵌套段留占位注释。"""
    lines = text.split("\n")
    n = len(lines)
    depth = [0] * (n + 1)
    d = 0
    in_block_comment = False
    for i, ln in enumerate(lines):
        s = ln
        if in_block_comment:
            bi = s.find("*/")
            if bi < 0:
                s = ""
            else:
                s = s[bi + 2 :]
                in_block_comment = False
        while True:
            bi = s.find("/*")
            if bi < 0:
                break
            bj = s.find("*/", bi)
            if bj < 0:
                s = s[:bi]
                in_block_comment = True
                break
            s = s[:bi] + s[bj + 2 :]
        s = s.split("//")[0]
        d += s.count("{") - s.count("}")
        depth[i + 1] = d
    decls = []
    for i, ln in enumerate(lines):
        m = DECL.match(ln)
        if m and m.group(3) in ("class", "enum", "interface", "struct"):
            decls.append((i, depth[i], m.group(4)))
    segments = []
    for i, d, name in decls:
        o = i
        while o < n and depth[o + 1] <= d and o - i <= 5:
            o += 1
        if o >= n or o - i > 5 or depth[o + 1] <= d:
            segments.append((i, i + 1, name))  # 单行类型（如一行 enum）
            continue
        j = o + 1
        while j < n and depth[j] > d:
            j += 1
        segments.append((i, j, name))
    owner = [-1] * n
    for k, (s, e, name) in enumerate(segments):
        for i in range(s, min(e, n)):
            owner[i] = k
    files = []
    for k, (s, e, name) in enumerate(segments):
        body = []
        i = s
        e = min(e, n)
        while i < e:
            if owner[i] == k:
                body.append(lines[i])
                i += 1
            else:
                nk = owner[i]
                body.append(
                    f"\t\t// [嵌套类型 {segments[nk][2]} -> {segments[nk][2]}.cs]"
                )
                i = max(i + 1, min(segments[nk][1], e))
        files.append((name, body))
    return files


def _write_classes(files: list, outdir: Path) -> int:
    """写类型文件，同名加 _1 后缀，写出 OSError 转 SourceError。"""
    used = {}
    count = 0
    for name, body in files:
        used[name] = used.get(name, 0) + 1
        fn = name if used[name] == 1 else f"{name}_{used[name] - 1}"
        try:
            (outdir / (fn + ".cs")).write_text(
                "\n".join(body).rstrip() + "\n", encoding="utf-8"
            )
        except OSError as e:
            raise SourceError(f"写出类型文件失败 {outdir/fn}.cs：{e}") from e
        count += 1
    return count


def _split_single_file(src: Path, outdir: Path) -> int:
    """单文件模式：拆成每类型一个文件。"""
    files = split_file(_read_utf8(src))
    if not files:
        raise SourceError(f"没有找到任何类型声明（class/enum/interface/struct）：{src}")
    return _write_classes(files, outdir)


def _split_project(src: Path, outdir: Path) -> int:
    """项目目录模式：递归收集 .cs，UTF-8 校验后复制，重名加后缀。"""
    try:
        files = sorted(p for p in src.rglob("*.cs") if p.is_file())
    except OSError as e:
        raise SourceError(f"遍历项目目录失败 {src}：{e}") from e
    if not files:
        raise SourceError(f"项目目录里没有 .cs 文件：{src}")
    used = {}
    count = 0
    for p in files:
        text = _read_utf8(p)
        stem = p.stem
        fn = stem
        if fn in used:
            fn = f"{stem}_{used[stem]}"
        used[stem] = used.get(stem, 1) + 1
        try:
            (outdir / (fn + ".cs")).write_text(text, encoding="utf-8")
        except OSError as e:
            raise SourceError(f"写出类型文件失败 {outdir/fn}.cs：{e}") from e
        count += 1
    return count


def split(workspace: Path, input_path: Path | None, output_path: Path | None) -> dict:
    """拆分源码到 workspace/kb/source/classes，返回摘要信息。"""
    if input_path:
        src = input_path
    else:
        # 默认：单文件 decompile 产物优先，--project 项目目录其次
        single = workspace / DEFAULT_INPUT
        src = single if single.is_file() else workspace / "src"
    outdir = output_path or workspace / DEFAULT_OUTPUT
    if not src.is_file() and not src.is_dir():
        raise WorkspaceError(
            f"输入不存在（先执行 decompile，或用 --input 指定源码文件/项目目录）：{src}"
        )
    _prepare_outdir(outdir, workspace)
    if src.is_dir():
        count = _split_project(src, outdir)
        mode = "项目目录"
    else:
        count = _split_single_file(src, outdir)
        mode = "单文件"
    print(f"拆分完成（{mode} 模式）: {count} 个类型文件 -> {outdir}")
    return {"mode": mode, "files": count, "output": str(outdir)}
