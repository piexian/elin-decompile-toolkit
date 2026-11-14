---
name: elin-decompile-toolkit
description: Extract and verify data from the game Elin (Unity) — decompile Elin.dll, parse the official Chinese language pack and binary game assets, diff game versions, write wiki pages with per-section source annotations, and build a RAG knowledge base, or set up and use Elin MCP for source lookup and runtime testing. Use when the user asks about Elin game mechanics, item/character names, official Chinese translations, recipe data, wiki articles, version changes, or wants a local LLM knowledge base from game data. Requires the game installed locally.
metadata:
  version: "0.1.0"
---

# Elin Decompilation Research Toolkit

A workspace-bound Python CLI that extracts official data from a locally installed copy of Elin, decompiles its source, compares Stable/Nightly versions, writes wiki drafts and builds an LLM knowledge base.

## Getting this toolkit (for the agent reading this)

You are probably reading this because `npx skills use` fetched it into a temporary directory, and that directory is already enough — this toolkit is a folder of Python scripts that run from wherever they sit, with no install step. Check whether you already have such a directory:

- if your instructions named a supporting-files directory, **work from it directly** and skip the rest of this section
- otherwise, or if you need the toolkit to persist across sessions, fetch or install it as below

**Run without installing.** Prints the skill to stdout and downloads the supporting files to a temp directory, which it names at the end. Redirect to a file first and read that, since the output is long:

```bash
npx skills use "https://github.com/piexian/elin-decompile-toolkit" --skill "elin-decompile-toolkit" > /tmp/elin-skill.txt
```

If GitHub is unreachable, the same command works against the GitCode mirror: use `https://gitcode.com/PIEXIAN/elin-decompile-toolkit.git` as the URL — a non-GitHub host must carry the `.git` suffix, or the CLI misparses it as a downloadable resource.

Resolve every relative path in this file — `scripts/`, `data/` — against that downloaded directory, not against the user's project.

**Install for reuse** when the user asks for it, or when you want the toolkit available in later sessions:

```bash
npx skills add piexian/elin-decompile-toolkit -g -y -a <agent> --copy
```

When GitHub is unreachable, point the same command at the GitCode mirror: the full URL `https://gitcode.com/PIEXIAN/elin-decompile-toolkit.git` (keep the `.git` suffix) or set `GH_HOST=gitcode.com` before the shorthand.

`-a` takes an agent name (`zcode`, `claude-code`, `codex`, …), or `*` for every agent the CLI knows about — note that `*` is the full registry, not the agents detected on this machine, so it writes a copy into every one of those directories (55 at the time of writing); name an agent unless the user wants all. `--copy` writes real files instead of symlinks, which keeps each agent's copy independent.

| Agent | Global skills directory |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.agents/skills/` (shares the canonical directory) |
| ZCode | `~/.zcode/skills/` |
| Generic `SKILL.md` readers (Cursor, …) | see that agent's documentation |

To install without Node.js, copy this whole folder instead, keeping `SKILL.md` beside the `scripts/` package:

```bash
cp -r . ~/.zcode/skills/elin-decompile-toolkit/
```

**Verify before relying on it**: confirm that `SKILL.md` and `scripts/` are siblings, then run `python -m scripts --help` and `python -m scripts check --game <game-dir>`.

## Optional: Elin MCP

The official Elin MCP is separate from the public `Elin-Decompiled` dump.

| Tooling | Use | Setup |
|---|---|---|
| `elin` | Remote source index, modding wiki, source-sheet schemas and game ids | Streamable HTTP at `https://mcp.elin-modding.net/`; no install, game files or API key |
| `elin-runtime` | Run C#, console commands, screenshots, logs and hot-loaded Harmony patches in the installed game | Elin Runtime MCP mod, Node.js 20+, client restart |
| Local decompile | Full-text search, offline work and versions newer than the index | .NET SDK 10+ and `ilspycmd` |

`Elin-Decompiled` is a static dnSpy dump, not an MCP server or an install target. It only contains part of the assemblies, so use it as a public reference; use the local decompile when the indexed source or the public dump is incomplete.

### Agent setup contract

1. Inspect the connected tool list first. `elin_guide`, `elin_find`, `elin_versions` and related names mean the remote knowledge server is already connected; `elin_instances`, `elin_eval`, `elin_hotload` and related names mean the runtime server is already connected. Do not add a duplicate configuration entry.
2. If a required server is missing, perform a read-only preflight and ask once whether the user wants the Agent to set up the missing MCP. The default is no installation. Continue with the local workflow when the user declines or the task does not need runtime control.
3. After approval, follow the official procedure at `https://mcp.elin-modding.net/llms.txt`: merge the `elin` HTTP entry into the existing client configuration, locate the game, install the matching stable/nightly Runtime MCP release from `https://github.com/gottyduke/Elin.Plugins/releases`, verify the release digest before extraction, configure `node "<mod>/bridge/elin-mcp.mjs" --config`, install the two skills when supported, and restart the client. If an npm package is needed, retry once with `--registry=https://registry.npmmirror.com` without changing the global registry.
4. Verify after restart with `elin_versions` and `elin_instances`. With the game closed, `elin_instances` returning no listening instance is correct. Compare the installed game version with the indexed channel before trusting source results.
5. Runtime MCP can execute C# sent by a local client and listens on `127.0.0.1` ports `27551`–`27560`. Tell the user to disable the mod for normal play or set `Enabled = false` under `[Listener]` in `dk.elinplugins.runtimemcp.cfg`.
6. If setup fails, report the dependency, command, exit or verification result, and the matching official page. Use the matching official page: [Elin MCP setup](https://mcp.elin-modding.net/llms.txt), [Elin MCP source](https://github.com/Elin-Modding-Resources/Elin.MCP), [Runtime MCP releases](https://github.com/gottyduke/Elin.Plugins/releases), [.NET SDK](https://dotnet.microsoft.com/download/dotnet/10.0), or [Node.js](https://nodejs.org/en/download). The verified domestic npm fallback is `https://registry.npmmirror.com` for npm packages only; no verified domestic mirror is assumed for the MCP endpoint or Runtime release.

The current official MCP/local-decompile route uses .NET SDK 10+ and Node.js 20+ for the runtime bridge. Do not silently downgrade the prerequisite or substitute an unverified mirror.

## Two iron rules (read before drawing any conclusion)

1. **Item/character names must come from the official language pack in `data/lang/` — never translate them yourself.** This holds even when consulting external wikis (Ylvapedia etc.): those sites only provide structural hints; every noun must be cross-checked against the official Chinese in the local language pack. If no Chinese exists, keep the English/Japanese original and mark it "awaiting official translation".
2. **Every mechanics conclusion must be grounded in code (`src/Elin.decompiled.cs`) or data (`data/`).** Community wikis (kamigame/ylvapedia etc.) are leads only — their versions drift far from the live game. Mark numbers that cannot be measured from data as "estimated".

## Writing wiki pages

Every section of a wiki page ends with a source annotation written as a MediaWiki comment. The comment does not render, so it costs the reader nothing, but it tells whoever re-checks the page — a human editor or the next agent — exactly which class, table row, language file, or asset produced the text above it. Write these by default. Drop them only when the user explicitly asks for a page without source annotations.

```
== 获得方式 ==
* 完成[[索林]]的遗物剧情后获得遗物槽位（EA 23.350 起），剧情结算时身上没有槽位会自动追加一个。
* 在装饰台制作：[[宝石]] ×1 ＋ [[基因]] ×1 ＋ [[树脂]] ×25 → '''宿卵'''（relic_lesser，暂无官方中文）。
<!-- 来源：槽位追加与「完成 into_darkness 任务自动赠送」两处逻辑 TraitSorin / RelicSlot（workspace/src/，按类拆到 workspace/kb/source/classes/）；配方与材料数量 workspace/data/things_full.jsonl id=<宿卵> 的 recipe 段 -->
```

Put the comment at the end of the section body, right before the next heading. A summary block at the top of the file is a useful supplement but never replaces the per-section comments.

Write the anchor that would let someone reproduce the section, choosing the first form that applies:

- **Mechanics and rules** — the class and method in the decompiled source, e.g. `Card.Decay`, `TraitBrewery`; use `workspace/src/` or `workspace/kb/source/classes/<Class>.cs`. Add the line range when you have it (`DNA.Relicize L113029`).
- **Numbers, fields, tables** — the extracted table and the row key: `data/things_full.jsonl` `id=1050`, `data/charas_full.jsonl` `_index=251` (`_id=373`), `data/elements.jsonl`, `data/categories.json`, `data/jobs.json`.
- **Names and text** — the language pack: `data/lang/Thing.json` (`id=1050`), or the in-game text file. The `.xlsx` files under `Package/_Lang_Chinese/Lang/CN/Game` are the translation tables, from which the language-pack JSON is exported.
  - **Untranslated entries** — some rows have misaligned language columns: `name` contains English while `name_EN` contains Japanese. Both cases indicate that no official Chinese translation exists. When exporting translation data, include every `*_EN` and `*_JP` column to preserve the original text.
  - **Random names** — a `*r` placeholder in a row indicates that a random name is generated rather than a fixed name. Look up `aka` or `detail` for the corresponding name or description, and explicitly state that the original entry uses a `*r` placeholder. If neither field provides the relevant information, state that as well.
- **Images** — the file in the game plus the crop parameters (`Package/_Elona/Texture/objs_C.png` tile 782 → row 24 col 14).
- **Computed numbers** — state the formula instead of the number alone, and mark it estimated: `<!-- 来源：属性 = race + job 直接相加（races.json norland + jobs.json bard），技能按 Element.GetSourceValue 等级缩放 → 推算 -->`.
- **Several claims in one section** — one comment holding one line per claim, still a single comment.

Sections that carry no sourced content (`== 导航 ==`, `== 参见 ==`, category tags) need no comment. `<!-- ... -->` is MediaWiki's comment syntax: it cannot nest and must not contain `--` inside, so keep one comment per section, on one line, and keep `来源` as the leading word so a grep for it lists every annotation in the page.

## Uploading images to the wiki

`[[File:...]]` stays a red link until the file is actually uploaded, so images are part of finishing a page, not an optional extra. The site publishes its rules at <https://elin.huijiwiki.com/wiki/MediaWiki:Uploadfiles-info>; the Chinese-language help summary lives in the maintainer workspace at `notes/图片上传规范.md`.

The site's own preference is to download the image from the matching page on the English wiki and keep its name, so you do not end up with a second copy of a file somebody already uploaded.

Every file needs a category, otherwise other editors cannot find it. Add it from the file page through the batch-description panel at the bottom right; in a batch you type only the category name, such as `Sprite` or `立绘`, not `[[分类:Sprite]]`.

| File type | Category |
|---|---|
| Character sprite (pixel figure) | `Sprite` |
| Character portrait / dialog art | `立绘` |
| Ability icon | `能力` |
| Spell icon | `魔法` |
| Element icon (fire, cold, nerve, …) | `领域` |
| Item icon | `物品` |
| Background (in-game UI and so on) | `背景` |
| The protagonist's 16-direction walk cycle | `PCC` |
| Steam achievement art | `成就` |

Naming rules:

- Portraits come out of `<game dir>/Package/_Elona/Portrait/`; upload them under the file's own name (`UN_<chara id>.png`). The English wiki's name is accepted too.
- Sprites must never be screenshots. Export them from the atlas (`scripts sprites`, see "Known pitfalls") or download them from the English wiki. A screenshot drags the UI background along and carries the wrong pixel scale.
- Names should say what the file is. `截图10395781826482364.jpg` gets deleted; `Elin_Npc_Sprite_Moyer.png` survives. English and Chinese names are both fine, mojibake is not.
- Local `_8x` previews stay local: the wiki scales pixel art in place with `{{像素图放大|[[File:x.png|240px]]}}`, so uploading an enlarged copy only adds a redundant file.

After overwriting an existing file, check the pages that use it and confirm they still render — the size arguments in `[[File:...|150px]]` and the `{{像素图放大}}` template both depend on the pixel dimensions of the file itself.

## Unified CLI

All extraction, decompilation, version comparison, lookup, corpus and page generation now use the workspace-bound CLI. Do not call removed legacy scripts.

```bash
python -m scripts --help
python -m scripts check --game <game-dir>
python -m scripts workspace init --channel stable --version <version> --game <game-dir> --root work
WS=work/stable/<version>
python -m scripts data extract --workspace "$WS" --game <game-dir> --all
python -m scripts decompile --workspace "$WS" --game <game-dir> --project
python -m scripts source split --workspace "$WS"
python -m scripts lookup thing 奶酪 --workspace "$WS"
python -m scripts corpus build --workspace "$WS"
python -m scripts chunks --workspace "$WS"
```

| Command | Purpose |
|---|---|
| `check` / `workspace init` | Validate the game and create a Stable/Nightly workspace with `version.json` |
| `data extract --all` | Export the language pack and strictly parse Thing, Material, Element, Chara, Zone, Quest and Religion tables |
| `decompile` | Run `ilspycmd`, normalize source encoding and record the DLL hash |
| `source split` | Split a single dump or project source into `kb/source/classes` for optional code chunks |
| `diff code` / `diff lang` | Compare two isolated workspaces by source type and language-table entity ID |
| `lookup` | Search official names and strict item/material data |
| `corpus build` / `chunks` | Build RAG corpus and AstrBot upload files inside the workspace |
| `pages` / `sprites` | Generate wiki drafts and crop verified atlas sprites |
| `pages gods` | Generate god/apostle drafts from strict SourceReligion data and official names |
| `ylvapedia fetch` / `revisions` | Cache optional Ylvapedia page wikitext with revision and fetch metadata |
| `pages enrich-ylvapedia <ids>` | Produce review-only character supplements without overwriting official fields |

`--game` overrides workspace discovery. Without it, the CLI checks the workspace registration, `ELIN_GAME_DIR` and Steam libraries. Every command fails non-zero on incomplete data; do not continue after a partial parse.

### Optional Ylvapedia enrichment

Use the official `https://ylvapedia.wiki/api.php` MediaWiki API for optional external supplements:

```bash
python -m scripts ylvapedia revisions --workspace work/stable/<version> --page "Elin:Bestiary/Unique_NPCs"
python -m scripts ylvapedia fetch --workspace work/stable/<version> --page "Elin:Bestiary/Unique_NPCs"
python -m scripts pages enrich-ylvapedia --workspace work/stable/<version> loytel poppy
python -m scripts pages gods --workspace work/stable/<version>
```

Use `SourceReligion` and the official language pack for god/apostle names and fields. Ylvapedia is only a supplementary source: cache page wikitext under the workspace, record page URL, revision ID, fetch time and response hash, and never overwrite official Chinese names or local source data. Fetch individual pages rather than crawling the site; honor `429`/`Retry-After`, use the MediaWiki etiquette, and respect the site's `ai-train=no` signal. `action=ask`/`askargs` are available, but do not assume every page has Semantic MediaWiki properties; use `parse/wikitext` and page-specific parsing.

The CLI outputs stay under `work/<channel>/<version>/`; never mix Stable and Nightly data or write generated output to repository-level `data/`, `src/` or `kb/`.

### Migration checks for agents

Before relying on an existing workspace, inspect the downloaded Skill directory and the chosen `work/<channel>/<version>/` directory:

- Require `scripts/`, `data/version_changes.json` and a valid workspace `version.json`.
- Check `channel`, version, DLL/assets hashes and that generated data, source and `kb/` all come from the same workspace.
- Reject mixed Stable/Nightly data, incomplete row/ID validation, or legacy root-level `data/`, `src/` and `kb/` used as current output.
- If a legacy script command or old output is found, stop the pipeline and migrate through the CLI; do not delete user files automatically. Report the failing command and evidence, then repair the new implementation before continuing.
- Do not create test files or upload local verification fixtures. Use temporary local fixtures outside the repository for validation and remove them afterwards.

## First-time setup

Prerequisites are Python 3.8+, an installed Elin copy, and .NET SDK 10+ plus `ilspycmd` only for decompilation. Node.js 20+ is needed only for the Runtime MCP bridge; Pillow is needed only for `sprites`.

The Agent first performs a read-only dependency and game preflight. It does not install by default. If a required dependency is missing, ask once whether the Agent should install it; after approval run the commands non-interactively and verify each version. On Windows, approved SDK/runtime installation can use:

```powershell
winget install --id Python.Python.3.12 --exact --silent --accept-source-agreements --accept-package-agreements
winget install --id Microsoft.DotNet.SDK.10 --exact --silent --accept-source-agreements --accept-package-agreements
winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-source-agreements --accept-package-agreements
```

Install the remaining tools only when needed:

```bash
dotnet tool install --global ilspycmd
python -m pip install Pillow
# If the official PyPI request fails, retry only this command:
python -m pip install Pillow --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

If installation fails, report the command, exit result and official page: [Python](https://www.python.org/downloads/), [.NET 10](https://dotnet.microsoft.com/download/dotnet/10.0), [ilspycmd/ILSpy](https://github.com/icsharpcode/ILSpy), [Pillow](https://pypi.org/project/Pillow/), [Node.js](https://nodejs.org/en/download) or [winget](https://learn.microsoft.com/windows/package-manager/winget/). Do not silently switch the MCP endpoint or Runtime release to an unverified mirror.

Create a workspace for every channel/version and never reuse its data between Stable and Nightly:

```bash
python -m scripts check --game <game-dir>
python -m scripts workspace init --channel stable --version <version> --game <game-dir> --root work
WS=work/stable/<version>
python -m scripts data extract --workspace "$WS" --game <game-dir> --all
python -m scripts decompile --workspace "$WS" --game <game-dir> --project
python -m scripts source split --workspace "$WS"      # optional code chunks
python -m scripts lookup thing 奶酪 --workspace "$WS"
python -m scripts corpus build --workspace "$WS"
python -m scripts chunks --workspace "$WS"
```

`data extract --all` stops on row-count, ID-set, JSON or asset errors. `decompile` records the DLL hash and normalizes output to UTF-8. Use `python -m scripts diff code` and `diff lang` only between complete workspaces.

## After a game update

Create a new workspace instead of overwriting the previous one:

```bash
python -m scripts workspace init --channel nightly --version <new-version> --game <game-dir> --root work
NEW=work/nightly/<new-version>
python -m scripts data extract --workspace "$NEW" --game <game-dir> --all
python -m scripts decompile --workspace "$NEW" --game <game-dir> --project
python -m scripts diff code --old work/stable/<old-version> --new "$NEW"
python -m scripts diff lang --old work/stable/<old-version> --new "$NEW"
```

Promote a Nightly snapshot to a Stable comparison only after checking the channel and manifest hashes. Compare rows by entity ID, never by `_index`; the CLI enforces this for language tables and strict data outputs.

When diffing the extracted tables, join rows **on the entity id, never on `_index`**: that field is the chain position inside the binary, so inserting new rows shifts every later one and a handful of real changes reads as thousands (23.358 added 18 thing rows; an `_index` join reported 2483 "changed" rows with tiles/value/pref all jittering, while the id join showed exactly 18 additions and the changes that actually happened).

## Version-diff lessons from practice

Taken from a real diff, EA 23.345 → 23.349 (four nightly batches):

- `scripts diff code` reported 62 changed types, yet after per-class checks **every previously researched mechanic survived byte-identical** — fermentation (`TraitBrewery` / `TraitAgingShelf` / `TraitDryBrick` / `TraitContainerCompost`), decay (`Card.Decay`), relics (`DNA` / `BodyCode`). The apparent changes were false signals: a deleted `Debug.Log` (`TraitFoodEggFertilized`), an equivalent short-circuit (`TraitCrafter`'s `Contains('@')`), a render parameter (`Card`'s `renderer.sync`). **Open the class and read the lines before concluding anything.**
- The bulk of the churn is rendering/UI refactoring (`BaseTileMap` ±1500 lines, `CardRenderer` ±280). Filter those out by churn first, then look at mechanics classes.
- Typical shape of an Elin update — look for: new mechanics (Time Stop: `ActTimeStop` / `ConTimeStop` + element 433 `negateTimeStop` + Stat 112), new monster families (`CTAG.nurse`, nurses now heal hostile targets too), new furniture and zones (`TraitDoorBig` + `Zone_AcademyRoran`), modding UI (`ModGroup`).
- **Language-pack deltas are the fastest index of new content**: `Package/_Lang_Chinese/Lang/CN/update.txt` lists each table's latest row count; diff it against the previous extraction (that update: Thing 2514→2585, Element 1075→1122, Chara 593→598, Category 140→141).
- Write conclusions so they can be re-verified: anchor them to class names and behavior, e.g. "`ConTimeStop.ConsumeTurn` returns `!owner.HasElement(433)` when `Master != owner`, so a target with element 433 keeps acting". Keep the Japanese/English original for officially untranslated entries instead of inventing a translation.

- **`value` churns nightly without any code change** (23.351: 969 rows, 23.353: 288, 23.354: 971, 23.356: 2589, 23.358: 982 — the same rows rewritten across builds). Mass value-only diffs are an export-tool recalculation, not balance design: never derive a mechanic from them, and refresh published wiki value tables only once a **Stable** build lands, not per nightly. Confirmed 2026-10-11: the Stable promotion (23.355) shipped **zero code changes and zero value changes** vs 23.354 Nightly — the churn settles at promotion, so the last Nightly's values are final.
- **A Stable promotion build can be a near no-op**: 23354 → 23355's only decompiled diff was 6 lines of assembly version metadata, yet the language pack still gained 17 official-Chinese fills (renames included). Don't skip the data pipeline just because the code diff is empty.
- **Summons can leave corpses since EA 23.353**: `Chara.SetSummon(duration, dropCorpse)` + `CINT.isSummonDropCorpse` (136); `Die()` still vanishes summons unless the flag is set. Callers that opted in: `TraitStrangeStatue` spawns and `TraitStrangePainting`'s living paintings (50/50 `paint_living` / `paint_living2`) — **the escort-quest case was reverted in EA 23.358** (`QuestEscort.ReleaseEscort` calls `SetSummon(60)` again), so keep this list version-stamped rather than eternal.
- **Story content arrives as a `QuestProgression` subclass plus its tables**: a new quest type class (fields/timing rules, e.g. `QuestNevernight.dateStarted` with a 24-hour gate in `Player`'s talk hook), its `SourceQuest` row with `type`/`drama`, `Quest.json` + `Person.json` + the character's `sorin.json`-style drama steps, and an auto-add line in the daily tick (`IsCompleted(prev) → Add(new, sponsor)`). All of that showed up in 23.358 with **zero Chinese** — the CN columns being untouched is not evidence that nothing new landed.
- **A data `tag` string only means something if `CTAG` has the matching member**: `Card.HasTag(CTAG x)` is literally `sourceCard.tag.Contains(x.ToString())`, so a new tag name in the item table needs a new enum member to be readable at runtime. EA 23.358 added `CTAG.fixedMat` (pin the created material to `materials.alias[AliasMaterialOnCreate]` instead of rolling one from `tierGroup`) together with the first tagged items — the four bunny-suit pieces.

## Building an AstrBot knowledge base

```bash
python -m scripts corpus build --workspace work/stable/<version>
python -m scripts source split --workspace work/stable/<version>   # only when --code is needed
python -m scripts chunks --workspace work/stable/<version>          # data/doc chunks
python -m scripts chunks --workspace work/stable/<version> --code  # include split source classes
```

`kb/embed_ready/` is the upload directory; `kb/MANIFEST.md` stays outside it. The manifest records the workspace version and the chunk setting. Use chunk size 2048, overlap 100, dense retrieval 15 and sparse retrieval 15 unless the target WebUI requires another fixed profile. Rebuild the workspace output after changing the size.

The default corpus contains official translation/data chunks only. Code chunks are opt-in and require `source split`; source lookup should normally use the `ilspycmd -p` project in `workspace/src/` or the local file-search plugin. Never upload a mixed Stable/Nightly workspace.

## Known pitfalls

- **ilspycmd output encoding has varied between builds — never assume.** The `ilspycmd X.dll > out.cs` redirect form follows the console code page — cp936 on Chinese machines. Reading it as UTF-8 raises `UnicodeDecodeError`, and bypassing with `errors='ignore'` turns Japanese into mojibake like `奢ޤα`, easily misread as "the game changed this string". But some builds' `-o <dir>` output is already UTF-8 (observed 2026-10-05 with ilspycmd 11.0), so a hard-coded `decode('cp936')` fails there too. Robust recipe: read bytes, try `utf-8-sig`, fall back to `cp936`, assert no U+FFFD, then assert the decompiled `[assembly: AssemblyFileVersion]` matches the game's `version.json`. cp932 fails to decode GBK output, which is how you can tell them apart. Also: ilspycmd emits CRLF on Windows — **normalize to LF before diffing**, otherwise a 2-line real change shows up as a whole-file phantom diff (2026-10-05: 51 real lines vs 458k lines unnormalized).
- **The cp936 redirect also silently corrupts un-encodable characters into `?` (2026-10-11).** When the redirect lands on cp936, chars outside GBK — `✓ ♪ ♥ ㎢` full-width ellipsis — are replaced by `?` *at write time*, and diffing against a UTF-8 baseline yields a dozen fake "code changes" (`"あ・・・"` → `"あ???"`). Neither the no-U+FFFD assert nor the version assert catches this, because `?` is legal ASCII. Fix: run ilspycmd from a batch file that does `chcp 65001` first (output is then real UTF-8; verified all special chars survive), and add an acceptance check that known special chars survive (`grep '✓'`). A diff full of `?` swallowing Unicode is an encoding artifact, not a game change.
- **Language-pack column semantics**: `name` is the default column, normally containing Chinese; `name_EN` contains English, and `name_JP` contains Japanese. Some untranslated rows have shifted columns: `name` contains English while `name_EN` contains Japanese. This column misalignment indicates that no official Chinese translation exists. When exporting corpus data, carry over every `*_EN` and `*_JP` column to preserve the original text.
  - **Random-name placeholders**: A `*r` value indicates that a random name is generated rather than a fixed name. It does not indicate whether an official Chinese translation exists. Look up `aka` or `detail` for the corresponding name or description, and explicitly state that the original entry uses a `*r` placeholder. If neither field provides the relevant information, state that as well.
- **The strict `data extract --all` command exports the language pack before parsing binary rows.** Do not run a partial table extraction against an incomplete workspace.
- **Serialized layout ≠ decompiled declaration — verify at the byte level, in both directions.** Some fields visible in the decompile are NOT in the stream (`SourceMaterial`'s `matColor`/`altColor`), and the reverse also happens: `SourceThing`'s `colorType` looks absent but IS serialized (it sits right after `defMat`; the first row's empty value once misaligned the whole chain). Also measured: `pref` is a bare `int[26]` with **no BitArray32 after it**, and `SourceJob.domain` is a paired `int[]`, not `string[]`. When a chain parse dies mid-table, hex-dump the rows around the break and diff two adjacent rows field by field instead of re-reading the class body.
- **Locating a table inside sharedassets0.assets**: search for the object's `m_Name` string (e.g. `\x0bSourceThing`); the header after it is `[int 1][editor name][source xlsx name][int row count]` followed by the rows. Chain-parse with three checks per row: `_index` increments from 0, `id` ∈ language pack, category/race/job ∈ their own tables. Strings are `len32 + UTF-8 + align4`, bools are 1 byte + align4, arrays are `count + elements`; base-class fields come first, declaration order = serialization order.
- **Character sprite cropping**: the character atlas is a plain PNG on disk — `Package/_Elona/Texture/objs_C.png` (the `pass chara` material's main texture, bound at runtime; **do not hunt for a "chara" texture inside .assets**, you won't find it). Grid is 128px cells, 32 per row, linear tile index from `charas_full.jsonl` `_tiles`: `row = tile // 32`, `col = tile % 32`; crop the cell, then trim to the alpha bounding box. Large sprites (`_idRenderData == "chara_L"`) live in `objs_L.png`. Character portraits (dialog art) are separate files: `Package/_Elona/Portrait/UN_<chara id>.png` — a character with no file there simply has no portrait.
- **`pref_ints` is a bare `int[26]` with no names — `SourcePref` exposes it as named properties.** Index map (from the `SourcePref` class, which lives in the decompile): 0 `shadow`/`test`, 1 `flags` (PrefFlag enum), 2 height-ish ×0.01, 3 `height`, 4/5 scale ×0.01, 6/7 plain ints, **8 `shadowX`, 9 `shadowY`, 10 `shadowRX`, 11 `shadowRY`**, 12–15 plain ints, 16 `liquidMod`, 17 ×0.01, 18–20 plain ints, 21 `liquidModMax`, 22 `_bits1`, 23 `hatY`/`defaultAltitude`, 24 `heightFix` ×0.01, 25 `scaleTex`. The only consumer of the `R`/`B` variants is `AddShadow(float x, float y, float z, ShadowData.Item s, SourcePref pref, int dir, bool snow)`, which picks `dir < 2 ? (flag ? shadowRX : shadowX) : (flag ? shadowBRX : shadowBX)` for X and the same shape for Y, all scaled by 0.01, with `flag = dir % 2 == 1` marking a mirrored direction. A version diff that only moves four adjacent pref values is a **drop-shadow nudge**, not a stat change — that is exactly how the 23.352 Patch 1 update touched `bigdoor1R` and nothing else in 2587 item rows.
- **A field name can mean two different variables.** `Act.TC` / `Act.CC` / `Act.TP` are **static** fields on `Act`, while `AttackProcess` declares same-named **instance** fields that shadow them — so a bare `TC` inside `AttackProcess` and an explicit `Act.TC` are different variables, and only the latter is process-wide. Check the qualifier and the call chain before naming a culprit: on the throw path (`ActThrow` → `AttackProcess.Perform(count, hasHit)`) the reachable write to the shared field is `Chara.DoHostileAction`, when a stealthed chara is spotted at range and fires a nested throw; `AttackProcess.Attack()`'s protection-interception callback, its sub-attack helper and `ActMeleeCounter` are **not** on that chain. The 23.352 Patch 1 fix in `ActThrow` snapshots and restores these fields around the throw attack precisely so a leaked target cannot reach the follow-up TraitErohon / DoHostileAction / training-dummy logic.
- **A C# language server needs a project, not a pile of `.cs` files**: serving the source dir to `astrbot_plugin_self_file_search`'s LSP tools only works when the dir is the `ilspycmd -p` output (`Elin.csproj` + files that keep their `using` headers). Loose directories throw `System.Exception: no or .csproj/.fsproj or sln files found` at startup, and `scripts source split`'s per-class split is unusable for this because those files were cut out of a single dump and carry no `using` lines.
- **Version diffing**: archive the old decompile before regenerating. `scripts diff code` shows which classes changed, but empty shells and pure-render classes are mostly noise.
- **Never put intermediate files in `/tmp`**: Git Bash and Windows Python resolve it differently; use project-relative paths.
- **Entities lose their names when packed**: after packing several entities into one heading section, only the first entity's title survives. Every entity's body must carry a `**Name (table id=xxx)**` line, otherwise later entities in the same section lose their id and primary name.

## Reference files

- `AGENTS.md` — repo conventions (auto-read by most agents): repo layout, generated-data paths, key locations, the iron rules. For workflows, this file wins.
