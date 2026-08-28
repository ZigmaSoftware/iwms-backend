# 06 — .gitignore and Secrets

## The principle

Git history is permanent and shared. Anything committed once is on every
clone and every fork of the repo, forever, even after you delete the file in
a later commit. So the rule is simple:

> **Credentials never enter git. Not once, not "temporarily", not in a
> comment, not in a `.txt` file.**

## What is ignored, and why

### `.env` — machine-specific secrets

```gitignore
.env
.env.*
!.env.example
```

This holds the real database password, the SMTP account password, and the
API keys. It differs per machine anyway, so tracking it would break your
colleagues even if it were safe — which it is not.

`.env.example` is the exception (`!.env.example`): it lists every key with
empty or safe placeholder values, so a new developer knows exactly what to
fill in. **When you add a new setting to `.env`, add the key to
`.env.example` in the same commit** — otherwise the next person's setup
fails with a confusing error.

### `app/migrations/` — generated per machine

```gitignore
**/migrations/*
!**/migrations/__init__.py
```

A deliberate team decision to avoid constant migration-numbering conflicts.
The cost is that the schema is not reproducible from git. Explained fully in
[02-database-and-env.md](02-database-and-env.md), including why it must
change before this goes to production with data that matters.

### Generated output — never commit

```gitignore
__pycache__/     *.py[cod]        # compiled Python
.venv/ venv/ env/                 # the virtualenv — rebuild with `uv sync`
staticfiles/                      # collectstatic output
media/                            # user uploads — belong on the server, not in git
*.log  db.sqlite3                 # logs and local databases
.pytest_cache/  .coverage  coverage.xml  htmlcov/   # test output
build/  dist/  *.egg-info/
```

`media/` is worth calling out: those are photos users uploaded on a
particular server. They are not source code, they are often large, and
committing them mixes one deployment's data into everyone's clone.

Test output is the same story — `coverage.xml` is a ~450 KB generated file
that changes on every run. Regenerate it, don't track it.

### Per-machine and deploy artefacts

```gitignore
backend_sync.sh
cron.sh
*.deb
```

`backend_sync.sh` and `cron.sh` contain server-specific paths
(`/home/admin/...`) and belong to one machine's deployment, not to the
codebase. `*.deb` catches downloaded installers like `cloudflared` that were
committed by accident.

### Editor and OS files

```gitignore
.vscode/  .idea/  .DS_Store  Thumbs.db
```

Your editor settings are yours.

## Real leak found in this repo — read this

An audit of this repository found that **`.env` had been committed**, along
with `install.txt` containing a plaintext SSH password, an API key, and
server IPs. `coverage.xml`, `cloudflared-linux-amd64.deb`, `prompt.md` and
`backend_sync.sh` were tracked too.

Those files have now been removed from tracking (`git rm --cached`) and the
ignore rules fixed, so they will not be committed again. **But removing a
file from tracking does not remove it from history.** Anyone with a clone, or
with access to the remote, can still read the old values.

### What must still be done

Because those credentials are in the history, they should be treated as
compromised and rotated:

- [ ] MySQL password for the IWMS database user
- [ ] `SECRET_KEY` (note: changing it invalidates every issued JWT, so
      everyone gets logged out once — do it at a quiet time)
- [ ] SMTP account password (`EMAIL_HOST_PASSWORD`)
- [ ] `MY_API_KEY` and `ORS_API_KEY`
- [ ] The SSH password that was written in `install.txt`
- [ ] Any weighbridge/GPS keys shared with the frontend

Optionally, purge them from history with `git filter-repo` — but note that
rewrites history, so every developer must re-clone. Agree it with the team
first. Rotating the credentials is the part that actually closes the hole;
history rewriting only reduces the exposure of the old values.

## Habits that keep this from happening again

**Read `git status` before every commit.** Most leaks are one careless
`git add .`.

**Prefer explicit adds:**

```bash
git add app/ tests/        # not: git add .
```

**Check what you are about to commit:**

```bash
git diff --cached
```

**Check whether a file is ignored:**

```bash
git check-ignore -v .env
```

**Check nothing sensitive is tracked:**

```bash
git ls-files | grep -iE "\.env|secret|password|\.pem|\.key"
```

**Never put credentials in scratch files.** `install.txt`, `notes.txt` and
`prompt.md` are exactly where secrets end up. If you need to record a server
password, it belongs in the team's password manager, not the repo.

**If you do commit a secret:** say so immediately — the fix is rotating the
credential, and that only works if the team knows. Quietly deleting the file
in a follow-up commit does nothing; the value is still in history.

Next: [07-deployment-and-troubleshooting.md](07-deployment-and-troubleshooting.md).
