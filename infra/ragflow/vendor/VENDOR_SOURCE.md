# Vendored from infiniflow/ragflow

This directory is copied **verbatim** from the official `docker/` deployment
folder of [infiniflow/ragflow](https://github.com/infiniflow/ragflow) —
per the MVP build instructions: *"Use the stable documented Docker
deployment rather than rewriting RAGFlow."*

- **Source repo:** https://github.com/infiniflow/ragflow
- **Path:** `docker/`
- **Commit:** `16de4bfcb645c11142165cc37258ef3f0c9a665c`
- **Vendored on:** 2026-09-21

**Do not hand-edit files in this directory.** To customize the deployment
(ports, credentials, resource limits) for PakMang AI, use the sibling
`../docker-compose.override.yml` and `../.env.pakmang` in the parent
`infra/ragflow/` directory instead, and re-vendor by re-running the copy
from a fresh clone when upstream changes.

`oceanbase/`, `oceanbase-entrypoint.sh`, and `docker-compose-CN-oc9.yml`
were dropped — they're alternate storage backends / China-region mirrors
not needed for this deployment.

## Why this can't be started inside the Claude Code cloud sandbox

This deployment was authored in a sandboxed cloud dev environment whose
egress policy allows `git clone` from GitHub but blocks Docker Hub's blob
CDN (`docker pull` fails with 403 on every image, RAGFlow's included).
`docker compose up` against this folder will not work *in that sandbox*.
It is written to run correctly on a normal developer machine or server
with unrestricted internet access — see `../README.md` for deployment
instructions.
