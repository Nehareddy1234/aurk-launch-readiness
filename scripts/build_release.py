"""Build a source-only release from explicit paths, never from the recovery ZIP."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES=("app","migrations","nginx","deploy")
FILES=("wsgi.py","gunicorn.conf.py","requirements.txt","requirements-lock.txt","Dockerfile",".dockerignore",".env.example","docker-compose.yml","DEPLOYMENT.md","AURK_READINESS_REPORT.md","WEBSITE_DEPLOYMENT_PLAYBOOK.md")
SCRIPTS=("backup_store.py","backup_archive.py","restore_drill.py","production_smoke.py","operational_alert.py","check_host_health.py")


def release_files():
    paths=[p for folder in DIRECTORIES for p in (ROOT/folder).rglob("*") if p.is_file()]
    paths += [ROOT/name for name in FILES]
    paths += [ROOT/"scripts"/name for name in SCRIPTS]
    for path in sorted(paths):
        relative=path.relative_to(ROOT)
        if "__pycache__" in relative.parts or path.suffix in {".pyc",".pyo"}: continue
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT): raise RuntimeError("Release path escapes source root")
        if not path.is_file(): raise RuntimeError(f"Missing release file: {relative}")
        yield path,relative.as_posix()


def main():
    target=ROOT/"dist"/"aurk-release.zip"
    target.parent.mkdir(exist_ok=True)
    manifest={}
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as archive:
        for source,name in release_files():
            data=source.read_bytes()
            manifest[name]=hashlib.sha256(data).hexdigest()
            archive.writestr(name,data)
        archive.writestr("release-manifest.json",json.dumps(manifest,sort_keys=True,indent=2))
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".sha256").write_text(digest+"  "+target.name+"\n")
    print(f"Built {target.name}: {len(manifest)} source files; SHA256 {digest}")


if __name__=="__main__": main()
