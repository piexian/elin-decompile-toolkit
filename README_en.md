# Elin Decompilation Research Toolkit

> 简体中文版：[README.md](README.md)
>
> [!TIP]
> **Quick install: send this sentence to your Agent**
>
> ```bash
> Install the `piexian/elin-decompile-toolkit` Agent Skill for me. Prefer `npx skills add piexian/elin-decompile-toolkit -y`; if GitHub is unavailable, use `https://gitcode.com/PIEXIAN/elin-decompile-toolkit.git`. After installation, verify that `SKILL.md` and `scripts/` are siblings and run `python -m scripts --help`.
> ```
An [Agent Skill](https://skills.sh) for extracting official Elin data, decompiling source, comparing Stable/Nightly versions, generating wiki drafts and building a local knowledge base.

## Install

Requires a local Elin installation and Python 3.8+; decompilation also needs .NET SDK 10+ and `ilspycmd`. Sprite cropping needs Pillow.

```bash
npx skills add piexian/elin-decompile-toolkit -y
```

If GitHub is inaccessible:

```bash
npx skills add https://gitcode.com/PIEXIAN/elin-decompile-toolkit.git -y
```

For temporary use without installing:

```bash
npx skills use "https://github.com/piexian/elin-decompile-toolkit" --skill "elin-decompile-toolkit" > skill.txt
```

Common options:

```bash
npx skills add piexian/elin-decompile-toolkit -g                    # global
npx skills add piexian/elin-decompile-toolkit -a zcode -a codex     # selected agents
npx skills add piexian/elin-decompile-toolkit --copy                 # copy instead of symlink
```

You can also copy the whole directory into an Agent's skills directory, such as `~/.agents/skills/`, `~/.claude/skills/` or project `.agents/skills/`; keep `SKILL.md` beside `scripts/`.

The Agent checks dependencies first and does not install by default; after approval it runs non-interactively. Retry failed npm/PyPI commands with the documented domestic mirror only for that command. See [SKILL.md](SKILL.md) for dependency details.

## Optional: Elin MCP

| Service | Purpose |
|---|---|
| Remote `elin` | Query the source index, wiki, table schemas and IDs without a local install |
| `elin-runtime` | Control the running game: C#, commands, screenshots, logs and hot-loading |

Ask the Agent to follow the [official setup](https://mcp.elin-modding.net/llms.txt). Runtime requires its mod, Node.js 20+ and a client restart; disable Runtime MCP for normal play.

## Use

```bash
python -m scripts check --game <game-dir>
python -m scripts workspace init --channel stable --version <version> --game <game-dir> --root work
WS=work/stable/<version>
python -m scripts data extract --workspace "$WS" --game <game-dir> --all
python -m scripts decompile --workspace "$WS" --game <game-dir> --project
python -m scripts lookup thing cheese --workspace "$WS"
python -m scripts corpus build --workspace "$WS"
python -m scripts chunks --workspace "$WS"
```

Outputs stay in `work/<channel>/<version>/`; Stable and Nightly remain separate.

| Command | Purpose |
|---|---|
| `data extract --all` | Export official language data, items, materials, elements, characters, zones, quests and religions |
| `decompile` / `source split` | Decompile and split source into classes |
| `diff code` / `diff lang` | Compare source and language data between isolated versions |
| `lookup` | Search official Chinese/English/Japanese names and IDs |
| `corpus build` / `chunks` | Build the RAG corpus and AstrBot upload chunks |
| `pages` / `sprites` | Generate character, zone and god drafts and crop atlas sprites |
| `ylvapedia fetch` / `pages enrich-ylvapedia` | Cache and generate source-stamped external review supplements |

Official Chinese names and local game data take precedence; never self-translate. Ylvapedia is supplementary only. Detect strict UTF-8/GBK `ilspycmd` output; a language-pack `*r` means a random name, so look up `aka` or `detail` instead of treating it as a fixed original name. Do not mix versions or use partial parses.

See [SKILL.md](SKILL.md) for all options, version diffs, knowledge-base workflows, MCP installation and troubleshooting.
