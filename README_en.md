# Elin Decompilation Research Toolkit

> 简体中文版：[README.md](README.md)

An [Agent Skill](https://skills.sh) for AI agents: extract official data from a locally installed copy of Elin and decompile its source — look up official Chinese names of items and characters, verify mechanics against decompiled code, diff game versions, and build a local LLM knowledge base. With this skill installed, an agent answers Elin questions from real game data instead of memory or second-hand wiki information.

Pure Python standard library, no third-party dependencies.

## Install

Prerequisites: Elin installed locally (Steam installs are located automatically; for non-Steam copies set the `ELIN_GAME_DIR` environment variable). Decompiling additionally needs .NET SDK 8+ and `ilspycmd`.

### Option 1: skills CLI (recommended)

```bash
npx skills add piexian/elin-decompile-toolkit
```

The CLI lists the agents it detected for you to pick (Claude Code / Codex / Cursor / Gemini CLI / OpenCode and about twenty more); the master copy goes into `.agents/skills/` and the other directories get symlinks. Useful flags:

```bash
npx skills add piexian/elin-decompile-toolkit -g      # global instead of project-local
npx skills add piexian/elin-decompile-toolkit -a claude-code -a codex
npx skills add piexian/elin-decompile-toolkit -y      # non-interactive, for CI / agent runs
```

Node.js is needed for `npx` only; the skill itself does not depend on it.

### Option 2: manual copy

Copy the whole `elin-decompile-toolkit/` directory into your agent's skills directory, keeping the folder name:

| Agent | Global | Project |
|---|---|---|
| Universal (skills CLI master copy) | `~/.agents/skills/` | `.agents/skills/` |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.codex/skills/` | `.codex/skills/` |
| ZCode | `~/.zcode/skills/` | `.zcode/skills/` |
| Cursor / others that read SKILL.md | see their docs | see their docs |

The installed layout must be `<skills dir>/elin-decompile-toolkit/SKILL.md`, with `SKILL.md` and `scripts/` in the same folder — the scripts derive the workspace root from their own location and stop working if the layout is shuffled.

## What you can do with it

The agent follows `SKILL.md` automatically. Typical prompts:

- "How do I make cheese, and what tools does it need" — looks up the official name and game data first, then grounds the answer in decompiled code
- "What is the official Chinese name of a fertilized egg" — checks the language pack; when no Chinese exists it keeps the original text and marks it, rather than inventing a translation
- "The game updated — decompile it again and diff the changes" — runs the version-diff workflow and reports per-class changes
- "Build an AstrBot knowledge base from the game data" — produces upload-ready aggregated chunks

The two iron rules at the top of `SKILL.md` are the toolkit's core contract:

1. **Names come from the official Chinese language pack only — never self-translate**; keep the EN/JP original marked "awaiting official translation" when no Chinese exists.
2. **Mechanics conclusions must be grounded in decompiled code or game data**; community wikis are leads only.

## Running the scripts directly (without an agent)

The game path is auto-located (registry / `libraryfolders.vdf` / `appmanifest_2135150.acf`), or set `ELIN_GAME_DIR` / pass it as the first argument:

```bash
# 1. Official Chinese language pack xlsx → JSON (must run first; item extraction depends on it)
python scripts/lang_xlsx_to_json.py data/lang
# 2. Item rows and the material table
python scripts/extract_things.py    data
python scripts/extract_materials.py data
# 3. Decompile the main DLL (output follows the console code page — GBK on Chinese Windows,
#    so it must be converted back to UTF-8; see SKILL.md)
mkdir -p src
ilspycmd "<game dir>/Elin_Data/Managed/Elin.dll" > new.cs
python -c "d=open('new.cs','rb').read().decode('cp936'); open('src/Elin.decompiled.cs','w',encoding='utf-8',newline='\n').write(d)"
rm new.cs
# 4. Sanity check
python scripts/lookup.py 奶酪
```

## Scripts

| Script | Purpose |
|---|---|
| `steam_locate.py` | Auto-locates the game directory; run `python scripts/steam_locate.py` to verify |
| `lang_xlsx_to_json.py` | Official Chinese language pack xlsx → JSON |
| `extract_things.py` | Extract item rows (with recipes) from sharedassets0.assets |
| `extract_materials.py` | Extract the material table (incl. decay values) |
| `split_decompiled.py` | Split the single-file decompile into per-class files |
| `diff_by_class.py` | Attribute a version diff to classes, sorted by churn |
| `diff_lang.py` | Row-level diff of the language tables |
| `lookup.py` | All-in-one lookup (id / CN / EN / JP + recipes) |
| `gen_character_pages.py` | Generate character-page drafts in the fullest site format |
| `build_corpus.py` | Rebuild the RAG corpus (one .md per entity) |
| `build_embed_chunks.py` | Rebuild aggregated AstrBot upload chunks + MANIFEST.md |

The full workflows for version diffing and knowledge-base building are in `SKILL.md`; the "Version-diff lessons from practice" section there uses a real diff (EA 23.345 → 23.349) to show how to read per-class conclusions and how to find new content from language-pack deltas.

## Known pitfalls

- `ilspycmd` single-file output follows the Windows console code page — GBK on Chinese machines. Reading it as UTF-8 raises `UnicodeDecodeError`; bypassing with `errors='ignore'` turns Japanese into mojibake, easily misread as "the game changed this string".
- Untranslated rows in the language pack carry a `*r` placeholder in the `name` column; the real names sit in `name_JP` / `detail_JP` and similar columns, so export those too.
- `extract_things.py` needs the language pack to locate row starts — running it without the pack produces 0 rows (the script prints a warning).
- Never put intermediate files in `/tmp`: Git Bash and Windows Python resolve it differently.

## Directory structure

```
elin-decompile-toolkit/
├── SKILL.md            agent entry point (frontmatter + workflows + iron rules + pitfalls)
├── AGENTS.md           repo conventions (auto-read by most agents)
├── README.md           this file's Chinese original
├── README_en.md        this file
├── data/version_changes.json  version-change source table (rendered into the corpus)
└── scripts/            11 Python scripts
```

Generated data (`data/`, `src/`, `kb/`) stays out of the repo, see `.gitignore`.
