# Elin 反编译考据工具箱

> 英文版：[README_en.md](README_en.md)

> [!TIP]
> **懒人安装：把这句话发给你的 Agent**
>
``` bash
帮我安装 `piexian/elin-decompile-toolkit` 这个 Agent Skill。优先运行 `npx skills add piexian/elin-decompile-toolkit -y`；如果 GitHub 不可用，改用 `https://gitcode.com/PIEXIAN/elin-decompile-toolkit.git`。安装后确认 `SKILL.md` 和 `scripts/` 同级，并运行 `python -m scripts --help` 验证。
```
给 AI Agent 用的 [Agent Skill](https://skills.sh)：从本地《Elin》提取官方数据、反编译源码、比较 Stable/Nightly 版本、生成 wiki 草稿和本地知识库。

## 安装

需要已安装《Elin》和 Python 3.8+；反编译另需 .NET SDK 10+ 与 `ilspycmd`。图片裁剪需要 Pillow。

```bash
npx skills add piexian/elin-decompile-toolkit -y
```

国内 GitHub 访问不畅时：

```bash
npx skills add https://gitcode.com/PIEXIAN/elin-decompile-toolkit.git -y
```

只临时使用、不安装：

```bash
npx skills use "https://github.com/piexian/elin-decompile-toolkit" --skill "elin-decompile-toolkit" > skill.txt
```

常用安装参数：

```bash
npx skills add piexian/elin-decompile-toolkit -g                    # 全局安装
npx skills add piexian/elin-decompile-toolkit -a zcode -a codex     # 指定 Agent
npx skills add piexian/elin-decompile-toolkit --copy                 # 复制而非链接
```

也可手动把整个目录复制到 Agent 的 skills 目录，例如 `~/.agents/skills/`、`~/.claude/skills/` 或项目 `.agents/skills/`；保持 `SKILL.md` 与 `scripts/` 同级。

依赖由 Agent 先检查，默认不自动安装；你同意后静默执行。npm/PyPI 失败时只对当前命令回退国内镜像。安装细节见 [SKILL.md](SKILL.md)。

## 可选：接入 Elin MCP

| 服务 | 用途 |
|---|---|
| 远程 `elin` | 查询源码索引、Wiki、表结构和 ID，无需本地安装 |
| `elin-runtime` | 控制运行中的游戏，执行 C#、命令、截图、日志和热加载 |

让 Agent 按 [官方 MCP 流程](https://mcp.elin-modding.net/llms.txt) 配置；Runtime 需要 Mod、Node.js 20+ 和客户端重启。正常游玩时关闭 Runtime MCP。

## 使用

```bash
python -m scripts check --game <游戏目录>
python -m scripts workspace init --channel stable --version <版本> --game <游戏目录> --root work
WS=work/stable/<版本>
python -m scripts data extract --workspace "$WS" --game <游戏目录> --all
python -m scripts decompile --workspace "$WS" --game <游戏目录> --project
python -m scripts lookup thing 奶酪 --workspace "$WS"
python -m scripts corpus build --workspace "$WS"
python -m scripts chunks --workspace "$WS"
```

所有产物保存在 `work/<channel>/<version>/`，正式版和夜间版分开。

| 命令 | 用途 |
|---|---|
| `data extract --all` | 提取官方语言包及物品、材质、元素、角色、地点、任务和神祇 |
| `decompile` / `source split` | 反编译源码并按类拆分 |
| `diff code` / `diff lang` | 比较两个隔离版本的源码和语言表 |
| `lookup` | 按官方中/英/日名称或 ID 查询 |
| `corpus build` / `chunks` | 构建 RAG 语料和 AstrBot 上传块 |
| `pages` / `sprites` | 生成角色、地点、神祇草稿并裁剪图集 |
| `ylvapedia fetch` / `pages enrich-ylvapedia` | 缓存并生成带来源的外部补充审阅稿 |

官方中文名和本地游戏数据优先，禁止自译；Ylvapedia 只作补充。`ilspycmd` 输出严格按 UTF-8/GBK 检测，语言包 `*r` 保留原名占位；不要混用版本或使用部分解析结果。

完整参数、版本 diff、知识库、MCP 安装和故障处理见 [SKILL.md](SKILL.md)。
