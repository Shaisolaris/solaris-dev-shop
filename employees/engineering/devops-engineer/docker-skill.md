# Docker - optional, task-scoped containers

Read this reference when container work is part of the owner's task. Loading it
does not authorize installing Docker, starting Docker Desktop/the daemon, pulling
images, creating containers, or modifying persistent startup settings. Use an
existing project venv/runtime when it meets the task; containers are optional.

## Before container execution

1. Inspect the project's existing environment and container configuration. Use
   only the owned project and daemon/context named by the task; a remote Docker
   context can mutate a different machine.
2. Confirm the task covers the intended container, image, paths, network, ports,
   lifetime and cleanup. Existing explicit authorization is enough; do not ask
   again for each command. If setup is outside that scope, keep preparing local
   files and report the missing prerequisite instead of provisioning silently.
3. Use an already available image pinned by its reviewed `@sha256:` digest.
   Starting an existing container does not justify an image refresh. A missing
   image is a prerequisite; any download/build is a separate scoped operation.
4. Inspect entrypoint/user requirements. Prefer an unprivileged UID, no added
   capabilities, `no-new-privileges`, a read-only root filesystem and bounded
   CPU/memory/PIDs when the workload supports them. Validate the resulting
   configuration; do not call an untested hardened template operational.
5. Specify teardown before start. Use foreground disposable runs when practical;
   no restart policy, login item, system service or startup hook by default.

## Files and credentials

- Mount only the required project subdirectory, read-only unless the task needs
  writes. Use a dedicated output directory or named volume for generated data.
- Never mount the Docker socket, host root, home, SSH agent/tmux socket, browser
  profile, cloud credentials or another client's workspace as routine setup.
- Do not use `--privileged`, host PID/IPC or host networking as a default. An
  exceptional need requires an explicit access decision and a narrower alternative
  to be assessed first. An owner's broad coding request is not that decision.
- Use no network for offline work. For a necessary local listener, bind only to
  `127.0.0.1` on the selected port; do not publish it on all interfaces.
  Use a supported, patched engine; older Docker releases before 28.0.0 have
  known localhost-publication exposure on the same L2 segment.
- Containers share a host kernel. A writable bind mount can change the host's
  files, and Docker daemon access can confer host-level control. Separate project
  names/images do not establish a security boundary against hostile code.

## Example: bounded offline analysis

For an authorized container task with an already reviewed image whose entrypoint
accepts this command. Resolve both directories to the task's owned paths first.
A digest binds bytes, not the trustworthiness of the image publisher or its code.

```bash
: "${SOLARIS_DEV_IMAGE:?Select an already available reviewed image digest}"
: "${SOLARIS_INPUT_DIR:?Select the owned input directory}"
: "${SOLARIS_OUTPUT_DIR:?Select the owned output directory}"
if [[ ! "$SOLARIS_DEV_IMAGE" =~ ^[A-Za-z0-9./:_-]+@sha256:[a-f0-9]{64}$ ]]; then
  echo "A reviewed image digest is required; no container started." >&2
  exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
  echo "Select a non-root execution identity; no container started." >&2
  exit 1
fi
docker run --rm --pull=never --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --user "$(id -u):$(id -g)" --cpus=1 --memory=512m --pids-limit=128 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$SOLARIS_INPUT_DIR,dst=/input,readonly" \
  --mount "type=bind,src=$SOLARIS_OUTPUT_DIR,dst=/output" \
  "$SOLARIS_DEV_IMAGE" python /input/analyze.py --out /output/report.json
```

Do not run this example as a startup hook. For a long-running service explicitly
requested by the owner, prepare its exact config, local bind, secrets handling,
health check, resource limits and removal command before starting it. Stop it
when that authorized service lifetime ends. Do not silently add an auto-update,
watcher, scheduled refresh or restart policy.

## Third-party agent boxes and dependencies

No agent-box installer is required by Solaris. Do not download and execute a
`latest` self-extracting installer merely to prepare a client project. If the
owner actually selects such a tool, inspect its source, choose an exact version,
verify the publisher's digest/signature and review its mounts, credentials,
network and persistence before installation. Never invent a checksum or claim
verification from HTTPS alone.

## References

- [Docker daemon attack surface](https://docs.docker.com/engine/security/#docker-daemon-attack-surface)
- [Runtime privileges and capabilities](https://docs.docker.com/engine/containers/run/#runtime-privilege-and-linux-capabilities)
- [Published ports and loopback binding](https://docs.docker.com/engine/network/port-publishing/)
- [Bind mount access to host files](https://docs.docker.com/engine/storage/bind-mounts/)

Historical provenance: earlier revisions adapted host-cleanliness and per-project
container patterns from wrsmith108 and RchGrav. Their blanket Docker requirement,
automatic setup examples and isolation claims are superseded by this procedure.
