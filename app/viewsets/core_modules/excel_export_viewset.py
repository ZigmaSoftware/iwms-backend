"""Server-side Excel export (see app/services/excel_export.py).

POST /api/v1/exports/excel/
    {path, params?, columns?, file_name?, sheet_name?}
    -> 200 .xlsx of every row of that list endpoint the caller can see
       (Content-Disposition: attachment, X-Row-Count: <rows>)
    -> 400 {"detail": "..."} on invalid input or a failed export

Runs synchronously in the request (no background worker).
"""
from urllib.parse import quote, urlsplit

from django.http import HttpResponse
from django.urls import Resolver404, resolve
from rest_framework.response import Response
from rest_framework.views import APIView

from app.services.excel_export import API_PREFIX, ExportError, export_list_to_xlsx

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Endpoints that must never be replayed by an export.
_BLOCKED_PREFIXES = (f"{API_PREFIX}exports/", f"{API_PREFIX}swagger")


def _export_path(raw):
    """The list endpoint to export, as an /api/v1/... path, or None.

    Accepts a path relative to the API root ("masters/fuels/",
    "/masters/fuels/") or a full "/api/v1/..." path. No scheme, host,
    query string or fragment (filters go in ``params``).
    """
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw or "\\" in raw:
        return None
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or parts.query or parts.fragment or raw.startswith("//"):
        return None
    path = parts.path
    if ".." in path.split("/"):
        return None
    if not path.startswith(API_PREFIX):
        path = API_PREFIX + path.lstrip("/")
    if not path.endswith("/"):
        path = f"{path}/"
    if path == API_PREFIX or path.startswith(_BLOCKED_PREFIXES):
        return None
    try:
        resolve(path)
    except Resolver404:
        return None
    return path


def _clean_params(raw):
    if not isinstance(raw, dict):
        return None
    params = {}
    for key, value in raw.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)):
            params[str(key)] = [
                str(v).lower() if isinstance(v, bool) else str(v) for v in value if v is not None
            ]
        elif isinstance(value, bool):
            params[str(key)] = str(value).lower()
        elif isinstance(value, (str, int, float)):
            params[str(key)] = str(value)
        else:
            return None
    return params


def _clean_columns(raw):
    """[{"header", "field"}], None for "every field", or False if invalid."""
    if not raw:
        return None
    if not isinstance(raw, list):
        return False
    columns = []
    for column in raw:
        if not isinstance(column, dict):
            return False
        header = str(column.get("header") or "").strip()
        field = str(column.get("field") or "").strip()
        if not header or not field:
            return False
        columns.append({"header": header[:255], "field": field[:200]})
    return columns


def _bad_request(detail):
    return Response({"detail": detail}, status=400)


class ExcelExportView(APIView):
    """Download every row of a list endpoint as Excel in one request."""

    def post(self, request):
        path = _export_path(request.data.get("path"))
        if path is None:
            return _bad_request(
                "path must be an existing list endpoint under /api/v1/ "
                "(e.g. \"/transport-masters/fuels/\"), without host or query string."
            )
        params = _clean_params(request.data.get("params") or {})
        if params is None:
            return _bad_request("params must be an object of text, number, boolean or list values.")
        columns = _clean_columns(request.data.get("columns"))
        if columns is False:
            return _bad_request("columns must be a list of {header, field}.")
        file_name = "".join(
            ch for ch in str(request.data.get("file_name") or "") if ch.isprintable() and ch not in "/\\"
        ).strip()[:255] or "export.xlsx"
        if not file_name.lower().endswith(".xlsx"):
            file_name = f"{file_name}.xlsx"
        sheet_name = str(request.data.get("sheet_name") or "Export")[:31]

        try:
            content, row_count = export_list_to_xlsx(
                request, path, params=params, columns=columns, sheet_name=sheet_name
            )
        except ExportError as exc:
            return _bad_request(str(exc))

        response = HttpResponse(content, content_type=XLSX_CONTENT_TYPE)
        ascii_name = "".join(
            ch for ch in file_name.encode("ascii", "ignore").decode() if ch.isprintable() and ch != '"'
        ) or "export.xlsx"
        response["Content-Disposition"] = (
            f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name)}"
        )
        response["X-Row-Count"] = str(row_count)
        return response
