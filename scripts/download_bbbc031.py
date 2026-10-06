"""Download and safely extract the official BBBC031 v1 release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError


URLS: dict[str, str] = {
    "ground-truth": "https://data.broadinstitute.org/bbbc/BBBC031/BBBC031_v1_DatasetGroundTruth.csv",
    "full": "https://data.broadinstitute.org/bbbc/BBBC031/BBBC031_v1_dataset.zip",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_download(kind: str, path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if kind == "full":
        try:
            with zipfile.ZipFile(path) as archive:
                return archive.testzip() is None and len(archive.infolist()) > 0
        except zipfile.BadZipFile:
            return False
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            reader = csv.reader(handle, dialect)
            header = next(reader)
            first_row = next(reader)
        return len(header) >= 5 and len(first_row) == len(header)
    except (OSError, StopIteration, UnicodeDecodeError, csv.Error):
        return False


def _progress(blocks: int, block_size: int, total: int) -> None:
    downloaded = blocks * block_size
    if total > 0:
        percent = min(100.0, downloaded * 100 / total)
        print(f"\r  {min(downloaded, total) / 1_048_576:6.1f}/{total / 1_048_576:.1f} MiB ({percent:5.1f}%)", end="")
    else:
        print(f"\r  {downloaded / 1_048_576:6.1f} MiB", end="")


def download_file(kind: str, output: Path, force: bool = False) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    url = URLS[kind]
    target = output / url.rsplit("/", 1)[-1]
    if not force and valid_download(kind, target):
        print(f"Using verified existing file: {target} ({target.stat().st_size:,} bytes)")
        print(f"  sha256={sha256(target)}")
        return target

    partial = target.with_suffix(target.suffix + ".part")
    partial.unlink(missing_ok=True)
    print(f"Downloading {url}\n  -> {target}")
    request = urllib.request.Request(url, headers={"User-Agent": "CellScope-AI/0.1 BBBC031 evaluator"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as handle:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
                downloaded += len(chunk)
                _progress(downloaded // (1024 * 1024), 1024 * 1024, total)
        print()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc

    partial.replace(target)
    if not valid_download(kind, target):
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded file failed {kind} validation: {target}")
    print(f"Verified {target.stat().st_size:,} bytes; sha256={sha256(target)}")
    return target


def extract_archive(archive_path: Path, output: Path, force: bool = False) -> Path:
    destination = output / "extracted"
    marker = destination / ".extraction_complete"
    if marker.exists() and not force:
        print(f"Using existing extracted dataset: {destination}")
        return destination
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        for index, member in enumerate(members, start=1):
            resolved = (destination / member.filename).resolve()
            if root not in resolved.parents and resolved != root:
                raise RuntimeError(f"Unsafe path in archive: {member.filename}")
            archive.extract(member, destination)
            if index % 100 == 0 or index == len(members):
                print(f"\rExtracted {index}/{len(members)} files", end="")
    print()
    marker.write_text(f"archive_sha256={sha256(archive_path)}\n", encoding="utf-8")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["dataset", *URLS], default="dataset")
    parser.add_argument("--output", type=Path, default=Path("data/raw/bbbc031"))
    parser.add_argument("--no-extract", action="store_true", help="Download without extracting the ZIP")
    parser.add_argument("--force", action="store_true", help="Replace verified existing downloads")
    args = parser.parse_args()
    try:
        kinds = ["full", "ground-truth"] if args.kind == "dataset" else [args.kind]
        paths = {kind: download_file(kind, args.output, args.force) for kind in kinds}
        if "full" in paths and not args.no_extract:
            extract_archive(paths["full"], args.output, args.force)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
