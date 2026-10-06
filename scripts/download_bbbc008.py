"""Download, verify, and safely extract the official BBBC008 v1 release."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError


FILES = {
    "images": "https://data.broadinstitute.org/bbbc/BBBC008/BBBC008_v1_images.zip",
    "foreground": "https://data.broadinstitute.org/bbbc/BBBC008/BBBC008_v1_foreground.zip",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_zip(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return bool(archive.infolist()) and archive.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def download(name: str, output: Path, force: bool = False) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    url = FILES[name]
    target = output / url.rsplit("/", 1)[-1]
    if valid_zip(target) and not force:
        print(f"Using verified {target.name}: {target.stat().st_size:,} bytes; sha256={sha256(target)}")
        return target
    partial = target.with_suffix(target.suffix + ".part")
    partial.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "CellScope-AI/0.1 external-validator"})
    print(f"Downloading {url}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as handle:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
                downloaded += len(chunk)
                suffix = f"/{total / 1_048_576:.1f}" if total else ""
                print(f"\r  {downloaded / 1_048_576:.1f}{suffix} MiB", end="", flush=True)
        print()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc
    partial.replace(target)
    if not valid_zip(target):
        target.unlink(missing_ok=True)
        raise RuntimeError(f"ZIP integrity validation failed: {target}")
    print(f"Verified {target.stat().st_size:,} bytes; sha256={sha256(target)}")
    return target


def extract(archives: dict[str, Path], output: Path, force: bool = False) -> Path:
    destination = output / "extracted"
    marker = destination / ".extraction_complete"
    expected = "\n".join(f"{key}={sha256(path)}" for key, path in sorted(archives.items())) + "\n"
    if marker.is_file() and marker.read_text(encoding="utf-8") == expected and not force:
        print(f"Using verified extraction: {destination}")
        return destination
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    root = destination.resolve()
    for group, archive_path in archives.items():
        group_root = destination / group
        group_root.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                resolved = (group_root / member.filename).resolve()
                if root not in resolved.parents:
                    raise RuntimeError(f"Unsafe archive path: {member.filename}")
                archive.extract(member, group_root)
            print(f"Extracted {len(archive.infolist())} entries from {archive_path.name}")
    marker.write_text(expected, encoding="utf-8")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw/bbbc008"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        paths = {name: download(name, args.output, args.force) for name in FILES}
        extract(paths, args.output, args.force)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
