"""Ylvapedia MediaWiki API client with workspace-local revisioned caches."""

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .errors import ElinToolError, ExitCode, WorkspaceError

API = "https://ylvapedia.wiki/api.php"
USER_AGENT = "elin-decompile-toolkit/1.0 (local verification; +https://github.com/piexian/elin-decompile-toolkit)"
MAX_RESPONSE = 8 * 1024 * 1024


class YlvapediaError(ElinToolError):
    """Ylvapedia request, response or cache failed."""

    exit_code = ExitCode.GAME_INCOMPLETE


def _page_name(page: str) -> str:
    page = page.strip()
    if not page or len(page) > 512 or "\x00" in page:
        raise YlvapediaError("Ylvapedia 页面名不能为空、超过 512 字符或含 NUL")
    return page


def _cache_path(workspace: Path, page: str, outdir: Path | None) -> Path:
    if outdir is not None:
        root = Path(outdir)
    else:
        root = workspace / "ylvapedia" / "cache"
    current = root
    while current != workspace and workspace in current.parents:
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise WorkspaceError(f"Ylvapedia 缓存路径是符号链接或非目录，拒绝操作：{current}")
        current = current.parent
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise WorkspaceError(f"Ylvapedia 缓存目录是符号链接或非目录，拒绝操作：{root}")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", _page_name(page)).strip("._")
    digest = hashlib.sha256(page.encode("utf-8")).hexdigest()[:16]
    return root / f"{safe or 'page'}-{digest}.json"


def _api_url(params: dict[str, str]) -> str:
    return API + "?" + urllib.parse.urlencode(params)


def _retry_delay(response: urllib.error.HTTPError | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 60.0)
            except ValueError:
                pass
    return min(2.0**attempt, 30.0)


def _request_json(params: dict[str, str]) -> tuple[dict, str, str]:
    url = _api_url(params)
    for attempt in range(4):
        response = None
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=30) as r:
                if r.status != 200:
                    raise YlvapediaError(f"Ylvapedia HTTP 状态异常：{r.status}：{url}")
                raw = r.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise YlvapediaError(f"Ylvapedia 响应超过 {MAX_RESPONSE} 字节：{url}")
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise YlvapediaError(f"Ylvapedia 响应顶层不是对象：{url}")
            if "error" in data:
                raise YlvapediaError(f"Ylvapedia API 错误：{data['error']}")
            return data, hashlib.sha256(raw).hexdigest(), url
        except urllib.error.HTTPError as e:
            response = e
            retryable = e.code == 429 or 500 <= e.code < 600
            if not retryable or attempt == 3:
                raise YlvapediaError(f"Ylvapedia HTTP {e.code}：{url}：{e.reason}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == 3:
                raise YlvapediaError(f"Ylvapedia 请求失败：{url}：{e}") from e
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise YlvapediaError(f"Ylvapedia 响应不是有效 UTF-8 JSON：{url}：{e}") from e
        delay = _retry_delay(response, attempt)
        print(f"Ylvapedia 请求失败，{delay:g} 秒后重试（{attempt + 1}/3）")
        time.sleep(delay)
    raise YlvapediaError(f"Ylvapedia 请求失败：{url}")


def _write_cache(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise WorkspaceError(f"创建 Ylvapedia 缓存目录失败：{e}") from e
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise WorkspaceError(f"Ylvapedia 缓存文件是符号链接或非普通文件：{path}")
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    except OSError as e:
        raise WorkspaceError(f"写入 Ylvapedia 缓存失败 {path}：{e}") from e


def _page_revisions(data: dict, page: str) -> tuple[str | None, str | None]:
    """读取 query.pages 的对象（v1）或数组（v2）结构。"""
    query = data.get("query")
    if not isinstance(query, dict):
        raise YlvapediaError(f"Ylvapedia revisions 响应缺 query：{page}")
    pages = query.get("pages")
    if isinstance(pages, list):
        items = pages
    elif isinstance(pages, dict):
        items = list(pages.values())
    else:
        raise YlvapediaError(f"Ylvapedia revisions 响应缺 query.pages：{page}")
    if len(items) != 1:
        raise YlvapediaError(f"Ylvapedia revisions 返回异常页面数：{page}")
    info = items[0]
    if not isinstance(info, dict) or "missing" in info or not info.get("revisions"):
        raise YlvapediaError(f"Ylvapedia 页面不存在或没有修订：{page}")
    revision = info["revisions"][0]
    if not isinstance(revision, dict):
        raise YlvapediaError(f"Ylvapedia 修订结构无效：{page}")
    revid = revision.get("revid")
    return (str(revid) if revid is not None else None, revision.get("timestamp"))


def revisions(
    workspace: Path, page: str, outdir: Path | None = None
) -> dict:
    """读取页面最新修订，缓存查询结果。"""
    page = _page_name(page)
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": page,
        "rvprop": "ids|timestamp",
        "format": "json",
        "formatversion": "2",
    }
    data, digest, url = _request_json(params)
    revid, timestamp = _page_revisions(data, page)
    payload = {
        "source": "Ylvapedia MediaWiki Action API",
        "endpoint": API,
        "operation": "revisions",
        "page": page,
        "url": url,
        "revid": revid,
        "timestamp": timestamp,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "response_sha256": digest,
        "revisions": data["query"]["pages"],
    }
    path = _cache_path(workspace, page, outdir).with_name(
        _cache_path(workspace, page, outdir).stem + ".revisions.json"
    )
    try:
        _write_cache(path, payload)
    except OSError as e:
        raise WorkspaceError(f"创建 Ylvapedia 缓存目录失败：{e}") from e
    print(json.dumps({"revid": revid, "timestamp": timestamp, "cache": str(path)}, ensure_ascii=False))
    return payload


def fetch(
    workspace: Path, page: str, outdir: Path | None = None
) -> dict:
    """读取并缓存页面 wikitext，记录可复核的修订信息。"""
    page = _page_name(page)
    params = {
        "action": "parse",
        "page": page,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }
    data, digest, url = _request_json(params)
    parsed = data.get("parse")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("wikitext"), str):
        raise YlvapediaError(f"Ylvapedia 响应没有 wikitext：{page}")
    revision_info = revisions(workspace, page, outdir)
    revid, timestamp = revision_info["revid"], revision_info["timestamp"]
    payload = {
        "source": "Ylvapedia MediaWiki Action API",
        "endpoint": API,
        "operation": "parse/wikitext",
        "page": page,
        "url": url,
        "revid": revid,
        "timestamp": timestamp,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "response_sha256": digest,
        "wikitext": parsed["wikitext"],
    }
    path = _cache_path(workspace, page, outdir)
    _write_cache(path, payload)
    print(json.dumps({"page": page, "revid": revid, "cache": str(path)}, ensure_ascii=False))
    return payload


def load_cache(path: Path) -> dict:
    """读取并验证本地 Ylvapedia 缓存。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise YlvapediaError(f"读取 Ylvapedia 缓存失败 {path}：{e}") from e
    except json.JSONDecodeError as e:
        raise YlvapediaError(f"Ylvapedia 缓存 JSON 损坏 {path}：{e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("wikitext"), str):
        raise YlvapediaError(f"Ylvapedia 缓存缺 wikitext：{path}")
    return data
