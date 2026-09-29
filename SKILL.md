---
name: elin-decompile-toolkit
description: Extract and verify data from the game Elin (Unity) — decompile Elin.dll, parse the official Chinese language pack and binary game assets, diff game versions, and build a RAG knowledge base. Use when the user asks about Elin game mechanics, item/character names, official Chinese translations, recipe data, version changes, or wants a local LLM knowledge base from game data. Requires the game installed locally.
---

# Elin Decompilation Research Toolkit

A set of Python scripts with zero third-party dependencies that extract official data from a locally installed copy of Elin and decompile its source: for writing wiki pages, answering mechanics questions, diffing game versions, and building an LLM knowledge base. Every script derives the workspace root from its own location, so the folder can live anywhere.

## Two iron rules (read before drawing any conclusion)

1. **Item/character names must come from the official language pack in `data/lang/` — never translate them yourself.** This holds even when consulting external wikis (Ylvapedia etc.): those sites only provide structural hints; every noun must be cross-checked against the official Chinese in the local language pack. If no Chinese exists, keep the English/Japanese original and mark it "awaiting official translation".
2. **Every mechanics conclusion must be grounded in code (`src/Elin.decompiled.cs`) or data (`data/`).** Community wikis (kamigame/ylvapedia etc.) are leads only — their versions drift far from the live game. Mark numbers that cannot be measured from data as "estimated".

## Scripts

| Script | Purpose | Invocation |
|---|---|---|
| `lang_xlsx_to_json.py` | Official Chinese language pack xlsx → JSON | `[<pack dir>] <outdir>`; auto-located when omitted |
| `extract_things.py` | Extract item rows (with recipes) from sharedassets0.assets | `[<game dir>] <outdir>`; auto-located when omitted |
| `extract_materials.py` | Extract the material table (incl. decay values) | same |
| `steam_locate.py` | Shared game-dir locator; also runnable standalone | `python scripts/steam_locate.py` |
| `split_decompiled.py` | Split the single-file decompile into per-class files | `[<src.cs>] [<outdir>]`; defaults to `kb/src/classes` |
| `diff_by_class.py` | Attribute a version diff to classes, sorted by churn | `<old.cs> <new.cs> <unified diff file>` |
| `diff_lang.py` | Row-level diff of the language tables | `<old lang dir> <new lang dir>` |
| `lookup.py` | All-in-one lookup (id / CN / EN / JP + recipes) | `python scripts/lookup.py 奶酪` |
| `gen_character_pages.py` | Generate character-page drafts (reads the game binary) | `[<game dir>]`; auto-located when omitted |
| `build_corpus.py` | Rebuild `kb/corpus` (RAG corpus) | no args |
| `build_embed_chunks.py` | Rebuild `kb/embed_ready` (AstrBot upload chunks) | `[WebUI chunk size]`, default 2048 |

Scripts that need the game path auto-locate it: the `ELIN_GAME_DIR` env var wins, then the Windows registry / platform default paths for Steam, then `libraryfolders.vdf` enumerates the libraries, then `appmanifest_2135150.acf` provides `installdir`, and the result is only accepted if `Elin_Data/Managed/Elin.dll` exists. The detected path is printed. `extract_materials.py` does `from extract_things import ...`, so always run it as `python scripts/extract_materials.py` — never `cd scripts` first.

## First-time setup

Prerequisites: Python 3.8+ (stdlib only) and .NET SDK 8+. The game must be installed.

```bash
dotnet tool install -g ilspycmd

# The language pack must be extracted first (extract_things uses it to locate row starts); game path is auto-located
python scripts/lang_xlsx_to_json.py data/lang
python scripts/extract_things.py    data
python scripts/extract_materials.py data

# Decompile: single-file output follows the console code page — GBK on Chinese Windows, must be
# converted back to UTF-8 (see pitfalls). Keep intermediates inside the project; never /tmp.
mkdir -p src
ilspycmd "<game dir>/Elin_Data/Managed/Elin.dll" > new.cs
python -c "d=open('new.cs','rb').read().decode('cp936'); open('src/Elin.decompiled.cs','w',encoding='utf-8',newline='\n').write(d)"
rm new.cs

python scripts/lookup.py 奶酪      # sanity check: items + recipes found means the pipeline works
python scripts/split_decompiled.py # split into kb/src/classes for per-class retrieval
```

## After a game update

```bash
cp src/Elin.decompiled.cs src/versions/Elin.decompiled.<old-version>.cs   # archive the old one
# re-run the three data steps + the decompile from "First-time setup", then diff:
diff -u src/versions/Elin.decompiled.<old>.cs src/Elin.decompiled.cs > src/versions/code_diff.txt
python scripts/diff_by_class.py src/versions/Elin.decompiled.<old>.cs src/Elin.decompiled.cs src/versions/code_diff.txt
python scripts/diff_lang.py <old lang dir> data/lang
```

`diff_by_class.py` attributes diff lines to their enclosing type and sorts by churn — the fastest way to tell whether an existing conclusion was touched by this update. The next section is a worked example.

## Version-diff lessons from practice

Taken from a real diff, EA 23.345 → 23.349 (four nightly batches):

- `diff_by_class.py` reported 62 changed types, yet after per-class checks **every previously researched mechanic survived byte-identical** — fermentation (`TraitBrewery` / `TraitAgingShelf` / `TraitDryBrick` / `TraitContainerCompost`), decay (`Card.Decay`), relics (`DNA` / `BodyCode`). The apparent changes were false signals: a deleted `Debug.Log` (`TraitFoodEggFertilized`), an equivalent short-circuit (`TraitCrafter`'s `Contains('@')`), a render parameter (`Card`'s `renderer.sync`). **Open the class and read the lines before concluding anything.**
- The bulk of the churn is rendering/UI refactoring (`BaseTileMap` ±1500 lines, `CardRenderer` ±280). Filter those out by churn first, then look at mechanics classes.
- Typical shape of an Elin update — look for: new mechanics (Time Stop: `ActTimeStop` / `ConTimeStop` + element 433 `negateTimeStop` + Stat 112), new monster families (`CTAG.nurse`, nurses now heal hostile targets too), new furniture and zones (`TraitDoorBig` + `Zone_AcademyRoran`), modding UI (`ModGroup`).
- **Language-pack deltas are the fastest index of new content**: `Package/_Lang_Chinese/Lang/CN/update.txt` lists each table's latest row count; diff it against the previous extraction (that update: Thing 2514→2585, Element 1075→1122, Chara 593→598, Category 140→141).
- Write conclusions so they can be re-verified: anchor them to class names and behavior, e.g. "`ConTimeStop.ConsumeTurn` returns `!owner.HasElement(433)` when `Master != owner`, so a target with element 433 keeps acting". Keep the Japanese/English original for officially untranslated entries instead of inventing a translation.

## Building an AstrBot knowledge base

```bash
python scripts/build_corpus.py          # kb/corpus: one .md per entity
python scripts/build_embed_chunks.py    # kb/embed_ready: aggregated upload chunks + MANIFEST.md
```

`kb/embed_ready/` is the **aggregated** upload directory — upload the whole folder to the AstrBot WebUI. Settings must match the directory: **chunk size 2048, overlap 100, dense retrieval 15, sparse retrieval 15**. Changing the chunk size means re-running `build_embed_chunks.py <new chunk size>`.

The packing mirrors AstrBot's own chunker (selected in `astrbot/core/knowledge_base/kb_helper.py`, implemented in `chunking/markdown.py`): `.md` files go through `MarkdownChunker`, every markdown heading becomes its own chunk, bodies within the chunk size are not split further, and `min_chunk_size` defaults to 0 — **adjacent short chunks are never merged**. That is why "one file per entity" makes every entity cost its own embedding call, an order of magnitude more calls than the content justifies.

## Known pitfalls

- **ilspycmd single-file output is GBK.** `ilspycmd X.dll > out.cs` follows the console code page — cp936 on Chinese machines. Reading it as UTF-8 raises `UnicodeDecodeError`, and bypassing with `errors='ignore'` turns Japanese into mojibake like `奢ޤα`, easily misread as "the game changed this string". Always `decode('cp936')` and re-encode to UTF-8. The multi-file output of `ilspycmd -o <dir>` is already UTF-8 and unaffected; cp932 fails to decode, which is how you can tell them apart.
- **Language-pack column semantics**: `name` = Chinese, `name_EN` = English, `name_JP` = Japanese (Chinese is the default column). Untranslated rows come in two shapes: the `*r` placeholder (`name` and `name_EN` both `*r`, the Japanese name tucked into `detail_JP`), or shifted columns (`name` holds English, `name_EN` holds Japanese). Both mean **no official Chinese exists**. When exporting corpus, carry over every `*_EN` / `*_JP` column and replace placeholders with "officially untranslated" — otherwise those entries are just `*r` at retrieval time.
- **`extract_things.py` needs the language pack to locate row starts.** Without `lang/Thing.json` in the output dir it silently produces 0 rows (the script prints a warning), so the language-pack step must run first.
- **Version diffing**: archive the old decompile before regenerating. `diff_by_class.py` shows which classes changed, but empty shells and pure-render classes are mostly noise.
- **Never put intermediate files in `/tmp`**: Git Bash and Windows Python resolve it differently; use project-relative paths.
- **Entities lose their names when packed**: after packing several entities into one heading section, only the first entity's title survives. Every entity's body must carry a `**Name (table id=xxx)**` line, otherwise later entities in the same section lose their id and primary name.

## Reference files

- `AGENTS.md` — repo conventions (auto-read by most agents): repo layout, generated-data paths, key locations, the iron rules. For workflows, this file wins.
