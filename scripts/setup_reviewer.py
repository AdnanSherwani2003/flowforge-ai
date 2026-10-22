#!/usr/bin/env python3
"""Initialize local reviewer without putting credentials in argv or logs."""
import argparse
import getpass
import os
import re
import secrets
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="reviewer")
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", args.username):
        raise SystemExit("Use a simple reviewer name of 1–64 characters")
    target = ROOT / ".env"
    if "FLOWFORGE_REVIEWER_PASSWORD_HASH=" in target.read_text():
        raise SystemExit("Reviewer already configured; no credentials changed")
    password = secrets.token_urlsafe(24) if args.generate else getpass.getpass("New reviewer password: ")
    if not 16 <= len(password) <= 200 or not password.isprintable() or "'" in password:
        raise SystemExit("Use 16–200 printable characters without single quotes")
    if not args.generate and password != getpass.getpass("Repeat reviewer password: "):
        raise SystemExit("Passwords did not match")
    code = "import sys; from pwdlib import PasswordHash; print(PasswordHash.recommended().hash(sys.stdin.read()))"
    result = subprocess.run(["docker","compose","run","--rm","--no-deps","-T","backend","python","-c",code],
        cwd=ROOT,input=password,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        raise SystemExit("Build backend image before setup (details suppressed)")
    digest = result.stdout.strip()
    if not digest.startswith("$argon2"):
        raise SystemExit("Unexpected hash; configuration unchanged")
    values = {"FLOWFORGE_REVIEWER_USERNAME":args.username,"FLOWFORGE_REVIEWER_PASSWORD_HASH":digest,
              "FLOWFORGE_REVIEWER_SESSION_SECRET":secrets.token_urlsafe(48)}
    if args.generate:
        values["FLOWFORGE_REVIEWER_PASSWORD"] = password
    addition = "\n# Local reviewer; plaintext password is not passed to containers.\n"
    addition += "".join(key+"='"+value+"'\n" for key,value in values.items())
    with target.open("a") as output:
        output.write(addition)
    os.chmod(target,0o600)
    print("Local reviewer configured; no secret values printed.")
    if args.generate:
        print("Generated password is retained only in ignored .env; inspect it privately.")
    print("Recreate only backend to load the configuration.")


if __name__ == "__main__":
    main()
