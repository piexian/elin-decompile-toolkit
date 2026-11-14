"""python -m scripts 入口：统一分发子命令。"""

import sys

from . import check, commands, workspace
from .errors import ElinToolError, ExitCode


def main(argv: list[str] | None = None) -> int:
    """CLI 入口，返回退出码。"""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("用法：python -m scripts <命令> [参数]（--help 查看详情）", file=sys.stderr)
        return ExitCode.USAGE
    if argv[0] in ("-h", "--help"):
        print(
            "用法：python -m scripts <命令> [参数]\n"
            "命令：\n"
            "  check      校验游戏目录完整性\n"
            "  workspace  管理版本工作区\n"
            "  data       提取官方数据到版本工作区\n"
            "  decompile  反编译游戏主 DLL 到工作区 src\n"
            "  diff       对比两个版本工作区的源码/语言包\n"
            "  corpus     构建 RAG 语料（kb/corpus）\n"
            "  chunks     打包 AstrBot 上传聚合文件（kb/embed_ready）\n"
            "  lookup     检索工作区数据\n"
            "  sprites    裁剪角色/物品精灵图\n"
            "  pages      生成 wiki 草稿（角色表/角色页/地点页）\n"
            "  source     按类拆分反编译源码（kb/source/classes）\n"
            "  ylvapedia  读取 Ylvapedia 补充页面和修订信息\n"
            "详情：python -m scripts <命令> --help"
        )
        return ExitCode.OK
    try:
        if argv[0] == "check":
            return check.main(argv[1:])
        if argv[0] == "workspace":
            return workspace.main(argv[1:])
        if argv[0] == "data":
            return commands.data.main(argv[1:])
        if argv[0] == "decompile":
            return commands.decompile.main(argv[1:])
        if argv[0] == "diff":
            return commands.diff.main(argv[1:])
        if argv[0] == "corpus":
            return commands.corpus.main(argv[1:])
        if argv[0] == "chunks":
            return commands.chunks.main(argv[1:])
        if argv[0] == "lookup":
            return commands.lookup.main(argv[1:])
        if argv[0] == "sprites":
            return commands.sprites.main(argv[1:])
        if argv[0] == "pages":
            return commands.pages.main(argv[1:])
        if argv[0] == "source":
            return commands.source.main(argv[1:])
        if argv[0] == "ylvapedia":
            return commands.ylvapedia.main(argv[1:])
    except ElinToolError as e:
        print(f"错误：{e}", file=sys.stderr)
        return e.exit_code
    print(f"未知命令：{argv[0]}", file=sys.stderr)
    return ExitCode.USAGE


if __name__ == "__main__":
    sys.exit(main())
