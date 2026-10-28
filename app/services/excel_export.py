"""Server-side Excel export of a list endpoint (synchronous).

``POST /api/v1/exports/excel/ {path, params, columns?}`` (see
app/viewsets/core_modules/excel_export_viewset.py) replays a GET of the
list endpoint *as the calling user* through Django's full middleware stack
(RequestFactory + BaseHandler), carrying the caller's own Authorization
header, so authentication, module permissions and company/project/location
scoping apply exactly as for a request from the browser. Every page is
fetched (following ``next``) and the rows are written to an .xlsx,
flattened the same way the browser export does (frontend
src/utils/exportExcel.ts): nested objects become dotted, title-cased
headers; lists and other values are JSON-encoded.
"""
import functools
import io
import json
import re
from urllib.parse import parse_qs, urlsplit

from django.core.handlers.base import BaseHandler
from django.test import RequestFactory

API_PREFIX = "/api/v1/"

# Rows requested per replayed GET (the shared LimitOffsetWithPage paginator
# otherwise serves PAGE_SIZE=20 rows per page), and the page cap.
EXPORT_PAGE_SIZE = 1000
EXPORT_MAX_PAGES = 100

# Client details copied onto the replayed request so audit/IP logging sees
# the real caller rather than the test-client defaults.
_CLIENT_META_KEYS = (
    "REMOTE_ADDR",
    "HTTP_X_FORWARDED_FOR",
    "HTTP_USER_AGENT",
    "HTTP_ACCEPT_LANGUAGE",
    # Web portals authenticate with a cookie named by this header.
    "HTTP_COOKIE",
    "HTTP_X_IWMS_PORTAL",
)

# Pagination params from the caller's current table view are dropped: the
# export always covers every row matching the filters.
_PAGINATION_PARAMS = {"page", "offset", "limit", "page_size"}


class ExportError(Exception):
    """A failure whose message is safe to show the user."""


_handler = None


def _get_handler():
    global _handler
    if _handler is None:
        handler = BaseHandler()
        handler.load_middleware()
        _handler = handler
    return _handler


def client_options(request):
    """What the replayed GET needs from the original request."""
    return {
        "host": request.get_host(),
        "secure": request.is_secure(),
        "auth": request.META.get("HTTP_AUTHORIZATION", ""),
        "meta": {key: request.META[key] for key in _CLIENT_META_KEYS if request.META.get(key)},
    }


def _replay_get(client, path, query):
    """GET ``path`` through the full middleware stack as the caller."""
    extra = {
        **(client.get("meta") or {}),
        "HTTP_HOST": client.get("host") or "localhost",
        "HTTP_ACCEPT": "application/json",
    }
    if client.get("auth"):
        extra["HTTP_AUTHORIZATION"] = client["auth"]
    request = RequestFactory().get(path, data=query or {}, secure=bool(client.get("secure")), **extra)
    response = _get_handler().get_response(request)
    try:
        body = json.loads(response.content or b"null")
    except ValueError:
        body = None

    if response.status_code == 401:
        raise ExportError("Your session has expired. Please log in and try again.")
    if response.status_code == 403:
        raise ExportError("You do not have permission to do this.")
    if response.status_code >= 400:
        detail = (body.get("error") or body.get("detail")) if isinstance(body, dict) else None
        raise ExportError(str(detail or f"The request failed (HTTP {response.status_code})."))
    return body


def fetch_all_rows(client, path, params):
    """Every row of the list endpoint ``path`` for the given filters."""
    query = {k: v for k, v in (params or {}).items() if k not in _PAGINATION_PARAMS}
    query["limit"] = str(EXPORT_PAGE_SIZE)
    rows = []
    for _ in range(EXPORT_MAX_PAGES):
        body = _replay_get(client, path, query)
        if isinstance(body, list):
            rows.extend(body)
            return rows
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise ExportError("The list endpoint returned an unexpected response.")
        rows.extend(body["results"])
        next_url = body.get("next")
        if not next_url:
            return rows
        parts = urlsplit(next_url)
        if parts.path != path:
            raise ExportError("The list endpoint returned an unexpected next page.")
        query = parse_qs(parts.query, keep_blank_values=True)
    raise ExportError("Too many rows to export. Narrow the filters and try again.")


# ------------------------------------------------------------------
# Excel output - mirrors frontend src/utils/exportExcel.ts
# ------------------------------------------------------------------

_ILLEGAL_XLSX_CHARS = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")
_ILLEGAL_SHEET_CHARS = re.compile(r"[\\/?*\[\]:]")
# Excel's per-cell text limit; longer values are cut rather than dropped.
_MAX_CELL_CHARS = 32767


def _cell_value(value):
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _ILLEGAL_XLSX_CHARS.sub("", value)
    return _ILLEGAL_XLSX_CHARS.sub(
        "", json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    )


@functools.lru_cache(maxsize=1024)
def _title(key):
    key = re.sub(r"[_-]+", " ", key)
    key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    key = re.sub(r"\s+", " ", key).strip()
    return re.sub(r"\b\w", lambda m: m.group(0).upper(), key)


def flatten_record(record, parent_key=""):
    flat = {}
    for key, value in record.items():
        export_key = f"{parent_key}.{key}" if parent_key else str(key)
        if isinstance(value, dict):
            flat.update(flatten_record(value, export_key))
        else:
            flat[_title(export_key)] = _cell_value(value)
    return flat


def _pick(record, field):
    value = record
    for part in field.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return _cell_value(value)


def build_xlsx(records, sheet_name="Export", columns=None):
    """``columns`` ([{"header", "field"}], dotted fields) picks and names the
    output columns; without it every field is exported, flattened."""
    import xlsxwriter

    records = [r for r in records if isinstance(r, dict)]
    if columns:
        headers = [c["header"] for c in columns]
        rows = [{c["header"]: _pick(r, c["field"]) for c in columns} for r in records]
    else:
        rows = [flatten_record(r) for r in records]
        headers = list(dict.fromkeys(key for row in rows for key in row))

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {
        "in_memory": True,
        # Cell text is data: never turn "=..." into a formula or text into links.
        "strings_to_formulas": False,
        "strings_to_urls": False,
        "strings_to_numbers": False,
    })
    sheet = workbook.add_worksheet(_ILLEGAL_SHEET_CHARS.sub("_", sheet_name)[:31] or "Export")
    if headers:
        sheet.write_row(0, 0, headers)
    for index, row in enumerate(rows, start=1):
        sheet.write_row(index, 0, [
            value[:_MAX_CELL_CHARS] if isinstance(value, str) else value
            for value in (row.get(header, "") for header in headers)
        ])
    workbook.close()
    return buffer.getvalue()


def export_list_to_xlsx(request, path, params=None, columns=None, sheet_name="Export"):
    """(xlsx bytes, row count) for every row of ``path`` visible to the
    user making ``request``. Raises ExportError on failure."""
    rows = fetch_all_rows(client_options(request), path, params)
    return build_xlsx(rows, sheet_name or "Export", columns), len(rows)
