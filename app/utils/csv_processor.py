import csv
import io
from typing import AsyncIterator


async def parse_csv_chunks_streaming(file_reader, chunk_size: int = 500) -> AsyncIterator[list[dict]]:
    """
    Parse CSV from a streaming file reader (async iterator of bytes chunks).
    Yields lists of parsed row dicts in chunks of chunk_size.
    Does NOT load the entire file into memory.
    """
    buffer = ""
    header = None
    chunk: list[dict] = []
    row_num = 0

    async for data in file_reader:
        if isinstance(data, bytes):
            data = data.decode("utf-8-sig")
        buffer += data

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")

            if header is None:
                # Parse header row
                reader = csv.reader(io.StringIO(line))
                header = next(reader)
                continue

            row_num += 1
            reader = csv.reader(io.StringIO(line))
            try:
                values = next(reader)
            except StopIteration:
                continue

            row_dict = {}
            for i, h in enumerate(header):
                row_dict[h] = values[i] if i < len(values) else ""
            row_dict["_row_num"] = row_num
            chunk.append(row_dict)

            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []

    # Handle remaining buffer (last line without trailing newline)
    if buffer.strip() and header is not None:
        row_num += 1
        reader = csv.reader(io.StringIO(buffer.strip()))
        try:
            values = next(reader)
            row_dict = {}
            for i, h in enumerate(header):
                row_dict[h] = values[i] if i < len(values) else ""
            row_dict["_row_num"] = row_num
            chunk.append(row_dict)
        except StopIteration:
            pass

    if chunk:
        yield chunk


async def parse_csv_chunks(content: bytes, chunk_size: int = 500) -> AsyncIterator[list[dict]]:
    """Convenience wrapper: parse from an in-memory bytes buffer using streaming logic."""

    async def _byte_reader():
        yield content

    async for chunk in parse_csv_chunks_streaming(_byte_reader(), chunk_size):
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


def format_csv_field(value: str) -> str:
    """Properly escape a CSV field: quote if it contains comma, quote, or newline."""
    if any(c in value for c in (",", '"', "\n", "\r")):
        return '"' + value.replace('"', '""') + '"'
    return value


def generate_csv_export_line(subscriber) -> str:
    """Generate a properly escaped CSV line for a subscriber."""
    email = format_csv_field(subscriber.email)
    name = format_csv_field(subscriber.name or "")
    status = format_csv_field(subscriber.status)
    tags_str = format_csv_field(";".join(subscriber.tags) if subscriber.tags else "")
    return f"{email},{name},{status},{tags_str}\n"
