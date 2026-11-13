"""Safe local QA commands: test/unit/integration/security/e2e/coverage/browser-setup."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from functools import lru_cache
from urllib.request import urlopen


@lru_cache(maxsize=1)
def secret_values():
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url
    secrets=[]
    for key,item in dotenv_values(".env").items():
        if item and any(word in key for word in ("PASSWORD","SECRET","TOKEN","DATABASE_URL","SMTP_KEY")):
            if len(item)>7: secrets.append(item)
            if "DATABASE_URL" in key:
                try:
                    password=make_url(item).password
                    if password and len(password)>3: secrets.append(password)
                except Exception: pass
    return sorted(secrets,key=len,reverse=True)


def redact(value):
    for item in secret_values(): value=value.replace(item,"[REDACTED]")
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["test","test-unit","test-integration","test-security","test-e2e","coverage","browser-setup"])
    parser.add_argument("--seed",type=int,default=101)
    args,extra=parser.parse_known_args()
    folder=Path("qa_artifacts");folder.mkdir(exist_ok=True)
    if args.command=="browser-setup":
        subprocess.run([sys.executable,"-m","playwright","install","chromium"],check=True)
        target=folder/"axe.min.js"
        target.write_bytes(urlopen("https://cdn.jsdelivr.net/npm/axe-core@4.10.3/axe.min.js",timeout=30).read())
        print("Local Chromium and pinned axe-core installed.");return
    selected={"test-unit":"tests/unit","test-integration":"tests/integration","test-security":"tests/security","test-e2e":"tests/e2e"}.get(args.command,"tests")
    command=[sys.executable,"-m","pytest",selected,"-v","-p","no:cacheprovider",f"--randomly-seed={args.seed}",f"--junitxml=qa_artifacts/{args.command}-{args.seed}.xml"]
    if args.command=="coverage":
        command += ["--cov=app","--cov-report=term-missing","--cov-report=html:qa_artifacts/coverage",f"--cov-report=json:qa_artifacts/coverage-{args.seed}.json"]
    command+=extra
    environment=os.environ.copy()
    environment.update(CUSTOMER_EMAILS_ENABLED="false",MAIL_SERVER="",WHATSAPP_ACCESS_TOKEN="")
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",env=environment)
    with (folder/f"{args.command}-{args.seed}.log").open("w",encoding="utf-8") as log:
        for line in process.stdout:
            safe=redact(line)
            log.write(safe);log.flush()
            print(safe,end="",flush=True)
    process.wait()
    # pytest XML also includes traceback locals; redact before delivery.
    xml=folder/f"{args.command}-{args.seed}.xml"
    if xml.exists(): xml.write_text(redact(xml.read_text(encoding="utf-8")),encoding="utf-8")
    raise SystemExit(process.returncode)


if __name__=="__main__": main()
