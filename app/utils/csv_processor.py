import csv
import io
from typing import AsyncIterator


async def parse_csv_chunks(content: bytes, chunk_size: int = 500) -> AsyncIterator[list[dict]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    chunk: list[dict] = []
    row_num = 0

    for row in reader:
        row_num += 1
        row["_row_num"] = row_num
        chunk.append(row)

        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []

    if chunk:
        yield chunk


def validate_csv_row(row: dict) -> tuple[dict | None, str | None]:
    email = row.get("email", "").strip().lower()
    if not email or "@" not in email:
        return None, f"Invalid email: {email!r}"

    name = row.get("name", "").strip() or None
    tags_raw = row.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []

    custom_fields = {}
    for key, value in row.items():
        if key not in ("email", "name", "tags", "status", "_row_num") and value:
            custom_fields[key] = value

    return {"email": email, "name": name, "tags": tags, "custom_fields": custom_fields}, None


def generate_csv_export_line(subscriber) -> str:
    tags_str = ";".join(subscriber.tags) if subscriber.tags else ""
    name = subscriber.name or ""
    return f"{subscriber.email},{name},{subscriber.status},{tags_str}\n"
