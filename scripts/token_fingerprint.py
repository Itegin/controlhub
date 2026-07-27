"""Print a fingerprint of AGENT_TOKEN so it can be compared across machines
without ever printing the raw secret.

Takes the .env path explicitly rather than relying on python-dotenv's
default search (which walks up from *this script's* directory, not the
caller's cwd -- that would silently resolve both invocations below to the
same repo-root .env instead of the two different files being compared).

    python scripts/token_fingerprint.py backend/.env
    python scripts/token_fingerprint.py agents/windows/.env

For the backend side, note this reads the host file. The token that
actually matters is what the *container* sees -- if compose's env_file
wiring has drifted from the file on disk (see commit dbaaa25), compare
against that instead:

    docker compose exec -T backend python -c \
        "import os,hashlib; t=os.environ.get('AGENT_TOKEN'); \
         print(f'length={len(t)} sha256_prefix={hashlib.sha256(t.encode()).hexdigest()[:12]}' if t else 'not set')"
"""
import hashlib
import os
import sys

from dotenv import dotenv_values

if len(sys.argv) != 2:
    print(f"usage: python {sys.argv[0]} <path-to-.env>")
    sys.exit(1)

env_path = sys.argv[1]
values = dotenv_values(env_path)
token = values.get("AGENT_TOKEN")

print(f"file: {os.path.abspath(env_path)}")
if token is None:
    print("AGENT_TOKEN: not set")
else:
    digest = hashlib.sha256(token.encode()).hexdigest()[:12]
    print(f"AGENT_TOKEN: length={len(token)} sha256_prefix={digest}")
