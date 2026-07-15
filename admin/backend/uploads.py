from __future__ import annotations

import gzip
import os
import secrets
from pathlib import Path

from werkzeug.datastructures import FileStorage

from pilot.archive import UnsafeArchiveError, validate_tar_archive

MAX_DATABASE_UPLOAD_BYTES = 4 * 1024**3
MAX_ARCHIVE_UPLOAD_BYTES = 8 * 1024**3
MAX_RESTORE_UPLOAD_BYTES = MAX_DATABASE_UPLOAD_BYTES + 2 * MAX_ARCHIVE_UPLOAD_BYTES + 1024**2
_CHUNK_SIZE = 1024**2
_SQL_MARKERS = (
    b"--",
    b"/*",
    b"SET ",
    b"CREATE ",
    b"INSERT ",
    b"DROP ",
    b"LOCK ",
    b"COPY ",
    b"PRAGMA ",
)


class UploadError(ValueError):
    pass


def create_upload_directory(bench_root: Path) -> Path:
    bench_root = bench_root.resolve()
    upload_root = bench_root / "tmp" / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    upload_root = upload_root.resolve()
    if not upload_root.is_relative_to(bench_root):
        raise UploadError("Upload directory resolves outside the bench.")

    directory = upload_root / secrets.token_hex(16)
    directory.mkdir(mode=0o700)
    return directory.resolve()


def save_database_upload(
    upload: FileStorage,
    directory: Path,
    *,
    max_bytes: int = MAX_DATABASE_UPLOAD_BYTES,
) -> Path:
    suffix = _database_suffix(upload.filename or "")
    path = _save(upload, directory, suffix, max_bytes)
    try:
        sample = _database_sample(path, suffix)
        if not _looks_like_sql(sample):
            raise UploadError("File is not a supported database backup.")
    except UploadError:
        path.unlink(missing_ok=True)
        raise
    return path


def save_archive_upload(
    upload: FileStorage,
    directory: Path,
    label: str,
    *,
    max_bytes: int = MAX_ARCHIVE_UPLOAD_BYTES,
) -> Path:
    suffix = _archive_suffix(upload.filename or "", label)
    path = _save(upload, directory, suffix, max_bytes)
    try:
        validate_tar_archive(path)
    except UnsafeArchiveError as exc:
        path.unlink(missing_ok=True)
        raise UploadError(f"{label.capitalize()} must be a safe tar archive: {exc}") from exc
    return path


def _save(upload: FileStorage, directory: Path, suffix: str, max_bytes: int) -> Path:
    directory = directory.resolve(strict=True)
    destination = (directory / f"{secrets.token_hex(16)}{suffix}").resolve()
    if destination.parent != directory:
        raise UploadError("Upload path resolves outside its storage directory.")

    size = 0
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            while chunk := upload.stream.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise UploadError(f"Upload exceeds the {max_bytes}-byte limit.")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def _database_suffix(filename: str) -> str:
    filename = filename.lower()
    if filename.endswith(".sql.gz"):
        return ".sql.gz"
    if filename.endswith(".sql"):
        return ".sql"
    raise UploadError("Database backup must be a .sql or .sql.gz file.")


def _archive_suffix(filename: str, label: str) -> str:
    filename = filename.lower()
    if filename.endswith((".tar.gz", ".tgz")):
        return ".tar.gz"
    if filename.endswith(".tar"):
        return ".tar"
    raise UploadError(f"{label.capitalize()} must be a .tar, .tar.gz, or .tgz file.")


def _database_sample(path: Path, suffix: str) -> bytes:
    try:
        if suffix == ".sql.gz":
            with gzip.open(path, "rb") as stream:
                return stream.read(8192)
        return path.read_bytes()[:8192]
    except (OSError, EOFError) as exc:
        raise UploadError("File is not a supported database backup.") from exc


def _looks_like_sql(sample: bytes) -> bool:
    sample = sample.lstrip().upper()
    return bool(sample) and b"\0" not in sample and sample.startswith(_SQL_MARKERS)
