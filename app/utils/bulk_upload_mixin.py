"""Single bulk-upload mechanism shared by every list page.

Every list page uploads the same way: Excel -> CSV -> POST
``<resource>/bulk-upload/`` (multipart ``file``). The import runs
synchronously inside that request and answers 200 with the standard
response::

    {
        "message": "Bulk upload completed",
        "success_count": <int>,
        "error_count": <int>,
        "total_count": <int>,
        "errors": [{"row": <csv data-row, 1-based>, "error": ...,
                    "data": <original csv row>}],
        "file_name": <uploaded file name>,
    }

Mix ``BulkUploadMixin`` into any ``ModelViewSet`` (first in the bases) to
enable the endpoint. Modules with complex import rules (FK-by-name
resolution, QR generation, ...) keep their own ``bulk_upload`` action and
build their response with ``bulk_upload_response`` so the shape matches.
"""

import csv
import io

from django.db import transaction
from rest_framework.decorators import action
from rest_framework.response import Response


def bulk_upload_response(message, success_count, errors, file_name=None, rows=None, **extra):
    """Standard bulk-upload response body.

    ``rows`` (the parsed CSV rows, in order) fills in ``data`` for errors
    that do not carry it yet, so the UI can show which records failed.
    ``extra`` keys are kept as-is (backward compatibility).
    """
    normalized = []
    for err in errors:
        err = dict(err)
        if "data" not in err:
            row_no = err.get("row")
            data = None
            if rows is not None and isinstance(row_no, int) and 1 <= row_no <= len(rows):
                data = rows[row_no - 1]
            err["data"] = data
        normalized.append(err)
    body = {
        "message": message,
        "success_count": success_count,
        "error_count": len(normalized),
        "total_count": success_count + len(normalized),
        "errors": normalized,
        "file_name": file_name,
    }
    body.update(extra)
    return body


class BulkUploadMixin:
    """Generic serializer-driven bulk upload (synchronous).

    Each CSV row is validated with the viewset's own serializer and saved
    through ``perform_create``, so the rules (tenancy stamping, audit
    logging, ...) are identical to creating the records one by one. Each
    row runs in its own savepoint, so a failing row never affects the
    others. Fully blank rows are skipped. Rejected rows echo the original
    CSV data so the UI can show *which* records failed.
    """

    bulk_upload_message = "Bulk upload completed"

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file") or request.data.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        try:
            raw = file.read() if hasattr(file, "read") else file
            decoded = raw.decode("utf-8-sig") if isinstance(raw, bytes) else str(raw)
            upload_name = getattr(file, "name", None) or "bulk_upload.csv"
        except Exception as exc:
            return Response(
                {"error": "Unable to decode CSV file", "detail": str(exc)},
                status=400,
            )

        try:
            reader = csv.DictReader(io.StringIO(decoded))
            if not reader.fieldnames:
                return Response(
                    {"error": "The uploaded file does not contain any data rows."},
                    status=400,
                )
            rows = list(reader)
        except Exception as exc:
            return Response(
                {"error": "Unable to parse CSV file", "detail": str(exc)},
                status=400,
            )

        success_count = 0
        errors: list[dict] = []

        for index, raw_row in enumerate(rows, start=1):
            # DictReader puts surplus cells under the key None; drop them.
            row = {key: value for key, value in (raw_row or {}).items() if key}
            if not any(
                (value.strip() if isinstance(value, str) else value) not in (None, "")
                for value in row.values()
            ):
                continue

            payload = {key: (None if value == "" else value) for key, value in row.items()}

            serializer = self.get_serializer(data=payload)
            if not serializer.is_valid():
                errors.append({"row": index, "error": serializer.errors, "data": row})
                continue
            try:
                # Savepoint per row: a DB error in one row must not poison
                # the transaction for the rows after it.
                with transaction.atomic():
                    self.perform_create(serializer)
            except Exception as exc:
                detail = getattr(exc, "detail", None)
                errors.append({"row": index, "error": detail if detail is not None else str(exc), "data": row})
                continue
            success_count += 1

        return Response(
            bulk_upload_response(
                self.bulk_upload_message, success_count, errors, file_name=upload_name
            )
        )
