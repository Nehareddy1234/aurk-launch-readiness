"""Read-only disk and upload-directory checks for the service account."""
import argparse
import os
from pathlib import Path
import shutil


def check_storage(path, min_free_gib=2):
    path = Path(path)
    if not path.is_dir():
        raise ValueError("Persistent uploads directory is missing")
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        raise ValueError("Persistent uploads directory is inaccessible to the service user")
    usage = shutil.disk_usage(path)
    if usage.free < min_free_gib * 1024**3:
        raise ValueError("Free disk space is below the configured reserve")
    if usage.free / usage.total < 0.1:
        raise ValueError("Less than ten percent disk space remains")
    return usage.free


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uploads", type=Path, required=True)
    args = parser.parse_args()
    try:
        free = check_storage(args.uploads)
    except (OSError, ValueError) as exc:
        print("Host storage check failed: " + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
        return 1
    print(f"Host storage check passed: {free / 1024**3:.1f} GiB free.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
