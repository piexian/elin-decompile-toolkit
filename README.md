# Elin 反编译考据工具箱

一套给 AI Agent 用的 [Agent Skill](https://skills.sh)，从本地安装的《Elin》提取官方数据并反编译源码：查物品/角色的官方中文译名、核对机制结论、比对游戏版本、构建本地 LLM 知识库。装上之后，Agent 回答 Elin 相关问题时会先查真实游戏数据，而不是凭印象或社区二手资料。

纯 Python 标准库，**唯一例外**：`crop_chara_sprite.py`（从图集切角色像素小人）需要 Pillow，其余脚本零第三方依赖。不切图就不必装。

```bash
pip install Pillow    # 仅 crop_chara_sprite.py 需要；装到实际运行脚本的那个解释器
```

## 安装

前置：本地已安装《Elin》（Steam 版会自动定位游戏目录，非 Steam 版用环境变量 `ELIN_GAME_DIR` 指定）。要跑反编译还需要 .NET SDK 8+ 和 `ilspycmd`。

### 方式一：skills CLI（推荐）

```bash
npx skills add piexian/elin-decompile-toolkit
```

CLI 会列出检测到的 agent 让你勾选（Claude Code / Codex / Cursor / Gemini CLI / OpenCode 等二十来个），主副本装到 `.agents/skills/`，其余目录建符号链接。常用参数：

```bash
npx skills add piexian/elin-decompile-toolkit -g      # 装到全局而不是当前项目
npx skills add piexian/elin-decompile-toolkit -a claude-code -a codex
npx skills add piexian/elin-decompile-toolkit -y      # 非交互，CI/Agent 里用
```

需要 Node.js（仅 `npx` 这一步用，skill 本身不依赖）。

### 方式二：手动复制

把整个 `elin-decompile-toolkit/` 目录复制到对应 agent 的 skills 目录，保持目录名不变：

| Agent | 全局目录 | 项目级目录 |
|---|---|---|
| 通用（skills CLI 的主副本位置） | `~/.agents/skills/` | `.agents/skills/` |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.codex/skills/` | `.codex/skills/` |
| ZCode | `~/.zcode/skills/` | `.zcode/skills/` |
| Cursor / 其他读 SKILL.md 的 agent | 参见其文档 | 参见其文档 |

装完的结构应该是 `<skills目录>/elin-decompile-toolkit/SKILL.md`，`SKILL.md` 必须和 `scripts/` 在同一层——脚本靠自身位置推导工作区根目录，挪乱就找不到数据了。

## 装上之后能做什么

Agent 会自动按 `SKILL.md` 里的流程干活。典型问法：

- 「奶酪怎么做、要什么工具」——先查官方译名和数据，再落到反编译代码给结论
- 「受精蛋的官方译名是什么」——查语言表，查无中文时保留原文并标注，不会自己编译名
- 「游戏更新了，重新反编译对比一下改动」——跑版本比对流程，输出逐类差异
- 「把游戏数据做成 AstrBot 知识库」——产出可直接上传的聚合语块

`SKILL.md` 开头有两条铁律，是这套工具的核心约定：

1. **译名一律以官方中文语言包为准，禁止自译**；查无中文的保留英文/日文原文并标注「待官方翻译」。
2. **机制结论必须落到反编译代码或游戏数据证据**，社区 wiki 只作线索。

## 手动跑脚本（不经过 Agent）

脚本也可以直接命令行使用，游戏路径会自动定位（注册表 / `libraryfolders.vdf` / `appmanifest_2135150.acf`），也可以用 `ELIN_GAME_DIR` 或第一个参数指定：

```bash
# 1. 官方中文语言包 xlsx → JSON（必须最先跑，物品提取靠它做行首识别）
python scripts/lang_xlsx_to_json.py data/lang
# 2. 物品行与材质表
python scripts/extract_things.py    data
python scripts/extract_materials.py data
# 3. 反编译主 DLL。-r 传引用程序集（不传则 Unity 类型解析失败，版本 diff 会被几万行
#    反编译器噪音淹没）；输出编码在不同构建间变过（cp936 / UTF-8 都出现过），不要假设
mkdir -p src
ilspycmd -r "<游戏目录>/Elin_Data/Managed" -o tmp_decomp "<游戏目录>/Elin_Data/Managed/Elin.dll"
python - <<'PY'
b = open('tmp_decomp/Elin.decompiled.cs','rb').read()
try:    t = b.decode('utf-8-sig')
except UnicodeDecodeError: t = b.decode('cp936')
assert '\ufffd' not in t, '转码事故'
open('src/Elin.decompiled.cs','w',encoding='utf-8',newline='\n').write(t.replace('\r\n','\n'))
PY
rm -r tmp_decomp
# 4. 自检
python scripts/lookup.py 奶酪
```

## 脚本一览

| 脚本 | 用途 |
|---|---|
| `steam_locate.py` | 自动定位游戏目录，可单独 `python scripts/steam_locate.py` 验证 |
| `lang_xlsx_to_json.py` | 官方中文语言包 xlsx → JSON |
| `extract_things.py` | 从 sharedassets0.assets 提取物品行（含配方） |
| `extract_materials.py` | 提取材质表（含 decay 腐烂值） |
| `extract_thing_rows.py` | 严格解析 SourceThing/Category/SpawnList → `things_full.jsonl` + `categories.json` + `spawnlists.json` |
| `extract_chara_rows.py` | 严格解析 SourceChara/Race/Job → `charas_full.jsonl` + `races.json` + `jobs.json` |
| `extract_zone_rows.py` | 严格解析 SourceZone → `zones_full.json`（id 与语言包不一致会报错退出） |
| `extract_quest_rows.py` | 严格解析 SourceQuest → `quests_full.json` |
| `extract_elements.py` | 解析 SourceElement 表（专长/技能/法术，含权重与槽位） |
| `split_decompiled.py` | 反编译单文件按类拆分，供按类检索 |
| `diff_by_class.py` | 版本间代码 diff 归属到类，按改动量排序 |
| `diff_lang.py` | 版本间语言表逐行 diff |
| `lookup.py` | 综合查询（id / 中 / 英 / 日 互查 + 配方） |
| `gen_character_pages.py` | 按站内最完整规格生成角色页草稿 |
| `gen_chara_table.py` | 用 `charas_full.jsonl` 重生成站内 603 行 `[[角色表]]` |
| `gen_zone_pages.py` | 按站内 `模板:地点导航` 分组生成缺失地点页草稿 |
| `crop_chara_sprite.py` | 从图集切角色像素小人/物品图标（**需要 Pillow**；站内不接受截图） |
| `build_corpus.py` | 重建 RAG 语料（每实体一个 .md） |
| `build_embed_chunks.py` | 重建 AstrBot 上传用的聚合语块 + MANIFEST.md |

`update_chara_ylv.py`（合入 Ylvapedia 补查数据）和 `gen_god_pages.py`（生成神页草稿）是维护者工作区专用：前者读写 `notes/ylvapedia/` 与 `drafts/characters/`，后者依赖尚无提取器的 `data/religions.json`，两者都不在本仓库里。

版本比对和知识库构建的完整流程见 `SKILL.md`，「版本比对实战要点」一节用 EA 23.345 → 23.349 的一次真实比对演示了怎么读 diff 结论、怎么从语言包增量找新内容。

## 已知坑

- `ilspycmd` 的输出编码**不要假设**：重定向形式走 Windows 控制台代码页（中文机器是 GBK），`-o` 目录形式在不同构建间既出现过 GBK 也出现过 UTF-8。直接按 UTF-8 读会抛 `UnicodeDecodeError`；用 `errors='ignore'` 绕开会让日文变成乱码，容易被误判成「游戏改了字符串」。落盘固定走「先试 `utf-8-sig`、失败退 `cp936`、断言无 U+FFFD」，并把 CRLF 归一成 LF 再 diff，否则 2 行真实改动会变成全文件 45.8 万行幻影 diff。
- 语言包里未翻译的行在 `name` 列填 `*r` 占位符，真正的名字在 `name_JP` / `detail_JP` 等列，导出语料时要把这些列一起带出来。
- `extract_things.py` 依赖语言包做行首识别，语言包没先跑会产出 0 行（脚本会警告）。
- 中间文件别放 `/tmp`：Git Bash 和 Windows Python 对它的解释不一致。

## 目录结构

```
elin-decompile-toolkit/
├── SKILL.md            Agent 入口（frontmatter + 工作流 + 铁律 + 版本比对实战要点 + 踩坑记录）
├── AGENTS.md           项目约定，多数 Agent 会自动读取（关键位置表 / wiki 惯例 / 词条索引）
├── README.md           本文件
├── data/version_changes.json  版本变动源表（结构化，build_corpus 渲染进语料）
└── scripts/            19 个 Python 脚本（仅 crop_chara_sprite.py 需要 Pillow）
```

生成的数据（`data/`、`src/`、`kb/`）不进仓库，见 `.gitignore`。
