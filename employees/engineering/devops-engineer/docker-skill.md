# Docker Skill - Containerized Development (wrsmith108) + a per-project agent box Per-Project Isolation (RchGrav)

> **Absorbed v0.3.0 (2026-04-25)** from `wrsmith108/docker-the coding agent-skill` (PRIMARY - host-cleanliness enforcement) + `RchGrav/the coding agentbox` (per-project isolation + 15+ pre-configured language profiles). the skill scanner v2 caught both. Use this for ANY container work.

## The two complementary patterns

| Pattern | Source | When to use |
|---------|--------|-------------|
| **Host-clean dev** (npm/node/python NEVER on host) | `wrsmith108/docker-the coding agent-skill` | Every project from day one - prevents `node_modules` pollution + Python venv chaos |
| **Per-project agent container** (each project gets its own image + the coding agent config) | `RchGrav/the coding agentbox` | When working on multiple clients in parallel - full isolation between Kellbell / CTT / Turnpike etc. |

These two layer together: a per-project agent box provides the per-project the coding agent environment; the docker-the coding agent-skill rules enforce that no commands leak to the host inside that environment.

---

## Pattern 1: Host-clean dev (wrsmith108)

### The single rule
> **Never run `npm`, `node`, `npx`, `tsx`, `python`, `pip`, `bundle`, `gem`, `composer`, or project scripts directly on the host.**
> Always use `docker exec <container-name> <command>` instead.

### Per-project config

`.the coding agent/docker-config.json`:
```json
{
  "containerName": "kellbell-dev-1",
  "baseImage": "node:20-slim",
  "port": 3000,
  "hasNativeModules": true
}
```

### Base image decision

| Project has | Use |
|-------------|-----|
| Native modules (sqlite, sharp, bcrypt, node-canvas) | `node:20-slim` (Debian-based, glibc) |
| Pure JS/TS only | `node:20-alpine` (smaller, musl) |
| PHP / WordPress | `php:8.3-fpm` + `nginx:alpine` |
| Python ML | `python:3.12-slim` + `uv` |
| Unsure | `node:20-slim` (safe default) |

> **Critical:** Alpine uses musl libc. Native modules built on glibc systems (your Mac) won't load (`ERR_DLOPEN_FAILED`). When in doubt, use `-slim`.

### docker-compose.yml template

```yaml
services:
  dev:
    image: node:20-slim
    container_name: ${CONTAINER_NAME:-app-dev-1}
    working_dir: /workspace
    volumes:
      - .:/workspace
      - node_modules:/workspace/node_modules    # named volume - install lives in container
    ports:
      - "${PORT:-3000}:3000"
    command: tail -f /dev/null                  # keep container alive for `docker exec`
    profiles: ["dev"]
volumes:
  node_modules:
```

### Daily commands

```bash
# Start container (once per session)
docker compose --profile dev up -d

# Install
docker exec kellbell-dev-1 npm install

# Run anything
docker exec kellbell-dev-1 npm test
docker exec kellbell-dev-1 npm run build
docker exec kellbell-dev-1 npm run lint
docker exec kellbell-dev-1 sh   # interactive shell

# Pre-flight check (before any command)
docker ps --filter name=kellbell-dev-1
```

### Why this matters
- **Clean host.** No `node_modules` pollution on the owner's Mac.
- **Reproducible.** Same Node 20 / Python 3.12 / PHP 8.3 across all collaborators.
- **No global packages.** No version conflicts between projects.
- **CI-safe.** Same container in dev = same container in GitHub Actions.

---

## Pattern 2: Per-project a per-project agent box (RchGrav)

### Install
```bash
wget https://github.com/RchGrav/the coding agentbox/releases/latest/download/the coding agentbox.run
chmod +x the coding agentbox.run
./the coding agentbox.run
# Adds ~/.local/bin/the coding agentbox symlink. Add ~/.local/bin to PATH.
```

### Per-project workflow
```bash
cd ~/projects/kellbell
the coding agentbox profile php database web    # Adds PHP + DB clients + nginx
the coding agentbox                              # Launches the coding agent inside the kellbell-specific container

cd ~/projects/ctt
the coding agentbox profile python ml database   # Different stack for CTT
the coding agentbox shell                        # Powerline zsh shell

cd ~/projects/turnpike
the coding agentbox profile javascript devops    # Yet another stack
the coding agentbox
```

Each project gets:
- Its own Docker image (`the coding agentbox-kellbell`, `the coding agentbox-ctt`, `the coding agentbox-turnpike`)
- Its own the coding agent auth state (`~/.the coding agentbox/<project>/.the coding agent/`)
- Its own shell history (`~/.the coding agentbox/<project>/.zsh_history`)
- Its own firewall allowlist (`~/.the coding agentbox/<project>/firewall/allowlist`)
- Its own Python venv (auto-created via `uv` if Python profile active)
- Its own profile config (`~/.the coding agentbox/profiles/<project>.ini`)

### The 15+ pre-configured profiles

**Core:** core, build-tools, shell, networking
**Languages:** c, rust, python (uv), go, flutter (fvm), javascript (nvm), java (SDKMan + Maven + Gradle + Ant), ruby, php
**Specialized:** openwrt, database, devops (Docker + K8s + Terraform), web (nginx + HTTP test clients), embedded (ARM toolchain + serial debuggers), datascience (Jupyter + R), security (scanners), ml

### Multi-instance pattern (parallel client work)
```bash
# Terminal 1
cd ~/projects/kellbell && the coding agentbox

# Terminal 2 (simultaneously)
cd ~/projects/ctt && the coding agentbox shell

# Terminal 3 (simultaneously)
cd ~/projects/turnpike && the coding agentbox profile rust go
```

All three run in parallel without conflict - separate images, separate auth, separate firewalls.

### Useful commands
```bash
the coding agentbox profiles              # List available profiles + descriptions
the coding agentbox profile status        # Current project's installed profiles
the coding agentbox info                  # Comprehensive project + system info
the coding agentbox install htop vim      # Add packages to project image
the coding agentbox allowlist             # View/edit network allowlist
the coding agentbox clean --project       # Wipe one project's data
the coding agentbox rebuild               # Rebuild current project's image
the coding agentbox tmux                  # Mounts host tmux socket inside container
```

---

## Decision matrix

| Scenario | Reach for |
|----------|-----------|
| New Solaristek client project (any language) | docker-compose with `.the coding agent/docker-config.json` + a per-project agent box profile for the stack |
| Quick one-off script | `docker run --rm -v "$PWD:/work" -w /work node:20-slim node script.js` |
| Multiple clients in parallel | a per-project agent box per project (full isolation) |
| WordPress / PHP shared-host work | docker-compose with `php:8.3-fpm` + `mysql:8` + `nginx:alpine` (then deploy via legacy FTP - see the ftp-deploy GIG at `solaris/gigs/ftp-deploy/`) |
| Python ML experiments | a per-project agent box profile `python ml datascience` |
| CI build matching dev | Same container image in GitHub Actions (publish `dev` image to GHCR, pull in workflow) |

---

## Anti-patterns

- ❌ `npm install` on the host → use `docker exec`
- ❌ Sharing `node_modules` volume across projects → use named volumes per project
- ❌ Alpine base image with native modules → use slim
- ❌ One mega `the coding agent --container` for all projects → use a per-project agent box per project
- ❌ Editing `~/.the coding agentbox/<project>/firewall/allowlist` outside a per-project agent box → use `the coding agentbox allowlist`
- ❌ Running `pip install` on host for "just this one experiment" → spawn a python container

---

## Source provenance

- wrsmith108 docker-the coding agent-skill: https://github.com/wrsmith108/docker-the coding agent-skill
- RchGrav the coding agentbox: https://github.com/RchGrav/the coding agentbox
- License: Both MIT
- Caught by: the skill scanner v2 (after v1 missed both)

## Comparator queue (Scout to re-evaluate quarterly)

- Anthropic-official `@anthropic-ai/the coding agent-code` Docker images (when published)
- `devcontainers/cli` - official VS Code dev containers spec (alternate per-project pattern)
