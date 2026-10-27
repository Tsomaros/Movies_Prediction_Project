"""Deploy the live app (Day 15): build the image here, push it to the private GHCR repo, and tell Render.

    uv run python scripts/deploy.py              # make deploy
    uv run python scripts/deploy.py --no-hook    # build and push only (Render keeps the running deploy)

Render can't build the image itself: the slim database, the models and the 8-bit MiniLM (about 470 MB) are
not in git. So the image is built from this checkout (run `make docker-build` first after a data or model
change: it rebuilds build/), tagged with the commit (`ghcr.io/tsomaros/movie-prediction:<commit>`, plus
`latest` for docker compose), pushed, and the deploy hook is called with that tag as `imgURL`, so each
deploy names an exact image and a rollback picks an earlier tag.

Refuses to run with uncommitted changes (the tag would lie). Needs `docker login ghcr.io` once, and in .env:
RENDER_DEPLOY_HOOK (Render -> the service -> Settings -> Deploy Hook; a secret) and VITE_SENTRY_DSN (the
frontend's Sentry DSN, baked into the bundle; empty = no frontend reports).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.parse
import urllib.request

from dotenv import load_dotenv

REPO = "ghcr.io/tsomaros/movie-prediction"


def run(*cmd: str) -> str:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE if cmd[0] == "git" else None).stdout or ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-hook", action="store_true", help="build and push, but don't deploy")
    args = parser.parse_args()
    load_dotenv()

    if run("git", "status", "--porcelain", "--untracked-files=no").strip():
        print("Commit first: the image is tagged with the commit it was built from.", file=sys.stderr)
        return 1
    commit = run("git", "rev-parse", "--short=12", "HEAD").strip()
    hook = os.environ.get("RENDER_DEPLOY_HOOK", "")
    if not args.no_hook and not hook:
        print("RENDER_DEPLOY_HOOK is not set in .env (or use --no-hook).", file=sys.stderr)
        return 1

    image = f"{REPO}:{commit}"
    run("docker", "build", "--platform", "linux/amd64", "-f", "backend/Dockerfile",
        "--build-arg", f"VITE_SENTRY_DSN={os.environ.get('VITE_SENTRY_DSN', '')}",
        "--build-arg", f"APP_RELEASE={commit}", "-t", image, "-t", f"{REPO}:latest", ".")
    run("docker", "push", image)
    run("docker", "push", f"{REPO}:latest")
    if args.no_hook:
        print(f"Pushed {image}; Render was not told.")
        return 0

    sep = "&" if "?" in hook else "?"
    with urllib.request.urlopen(f"{hook}{sep}imgURL={urllib.parse.quote(image, safe='')}", data=b"",
                                timeout=30) as r:
        print(f"Render accepted the deploy of {image} ({r.status}). Follow it in the dashboard, then:")
    print("  make smoke URL=https://<the service>.onrender.com WEB=https://<the service>.onrender.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
