# Containerized portable CI (Dagger) + dev tool/env manager (mise) - methodology

Depth pass 2026-06-14. Net-new TOOLCHAIN methodology only; NO upstream code bundled. Two current best-practice tools the employee had no doctrine on: Dagger (write CI pipelines as code that run identically locally and in any CI), and mise (one declarative manager for tool versions + env vars + project tasks).

Citation keys (this file): [dag] dagger/dagger Apache-2.0 ~15.7k* (created by Solomon Hykes + original Docker team) · [mise] jdx/mise MIT ~12.3k* rel 2026.x active. Both OSI-permissive, credible, well-starred, active.

Gate-0: CI doctrine was 100% YAML-runner-shaped (GitHub Actions primary + GitLab/CircleCI/Bitrise/Codemagic) with no programmable/containerized pipeline engine and no "run the exact CI locally" story. No tool/runtime version manager existed (no mise/asdf/.tool-versions anywhere). Dagger + mise = 0 hits across the employee's files. Both net-new.

NOTE on OpenTofu: OpenTofu was a candidate for this pass but is REJECTED as a duplicate - terraform-skill.md already covers it (dedicated "OpenTofu vs Terraform" section, default-to-OpenTofu for new post-2024 projects, MPL-2.0 note, migration path). Not re-absorbed.

---

## 1. Dagger - pipelines as code, run in containers [dag] - ABSORB (Apache-2.0)

Dagger is a programmable CI/CD engine: you write the pipeline in a real language (Go, Python, TypeScript - the SDKs) instead of YAML, and every step runs in a container via a BuildKit engine. The same pipeline runs on the developer's laptop and in whatever CI host (GitHub Actions, GitLab, etc.) calls it - local and CI behavior are identical.

- **When to reach for it:** complex pipelines whose YAML has become unmaintainable; "works in CI, fails locally" (or the reverse) debugging pain; pipelines you want to unit-test or share as modules; teams wanting to move off CI-vendor-specific YAML without a full migration. NOT a wholesale replacement for our GitHub Actions default on simple projects - Dagger runs INSIDE the existing CI runner; the YAML shrinks to "checkout + call Dagger."
- **The core idea (the win):** the pipeline is portable + reproducible because each step is a container with declared inputs. The function-call graph is the pipeline; Dagger caches each step by content, so unchanged steps are skipped across runs and across machines (shared cache). This is the determinism the rest of our doctrine demands (pin everything, no host pollution), expressed at the CI layer.
- **Host-clean by construction:** because steps run in containers, the runner does NOT need Node/Python/Go/etc. installed - it needs Docker/BuildKit + Dagger. This aligns exactly with the docker-skill host-clean rule (never `npm/node/python/pip` on the host); Dagger generalizes it to the whole pipeline.
- **Adoption pattern (incremental, low-risk):**
  1. Keep the GitHub Actions workflow as the trigger; replace the build/test STEPS with a single `dagger call` (or the official `dagger/dagger-for-github` action).
  2. Write the pipeline as a Dagger module in the team's language; expose functions like `test`, `build`, `lint`, `publish`.
  3. Developers run the SAME functions locally (`dagger call test`) to reproduce a CI failure exactly - no more "push to see if CI is green."
- **Pinning + supply chain:** pin the Dagger engine version and pin base images by digest inside the module, same as we pin actions by SHA and Terraform providers by exact version. The GitHub Action that invokes Dagger is still SHA-pinned per fleet doctrine (no floating `@v3`). Cache mounts must not cache secrets.
- **Secrets:** pass secrets as Dagger secret types (mounted, not baked into layers / not printed in logs), sourced from the CI's secret store; never inline. Same secret discipline as the rest of CI.
- **Boundary:** Dagger is the pipeline ENGINE; it does not replace IaC (Terraform/OpenTofu still provisions infra) or the GitOps deploy layer (ArgoCD/Flux still reconcile) - it builds/tests/packages and can call the deploy step, but the deploy reconciliation stays where gitops-skill.md puts it.
- **Red flags:** rewriting a trivial 20-line CI in Dagger for its own sake; caching secrets in a step; floating engine/base-image tags; assuming a runner without Docker/BuildKit can run it (it cannot - Dagger needs a container runtime).

## 2. mise - tool versions + env + tasks, one config [mise] - ABSORB (MIT)

mise (mise-en-place, formerly rtx) is a single tool that manages (a) versions of dev tools/runtimes (Node, Python, Go, Terraform/OpenTofu, jq, ...), (b) per-directory environment variables, and (c) project tasks - replacing asdf + direnv + a pile of `make`/npm-script glue. asdf-plugin compatible, written in Rust.

- **When to reach for it:** any repo where contributors need matching tool versions; replacing a stale `.nvmrc`+`.python-version`+`.terraform-version` scatter with one file; documenting the project's required commands so "how do I build/test/migrate this" is in the repo, not in someone's head; standardizing local dev across the fleet's machines.
- **Single source of truth: `mise.toml`.** Declares `[tools]` (pinned versions), `[env]` (env vars, incl. loading a dotenv file), and `[tasks]` (named commands). `mise install` makes the machine match; `mise x -- <cmd>` / shims run the right versions automatically when you `cd` into the project. This is the host-clean + pin-everything doctrine applied to the developer's machine and the CI runner alike.
- **Pin exact versions** in `[tools]` (e.g. a fixed Node/Python/Terraform version), same exact-pin rule we apply to actions, providers, and base images. Commit `mise.toml`; treat a version bump as a reviewed change.
- **Tasks make the repo self-documenting:** `[tasks.test]`, `[tasks.build]`, `[tasks.lint]`, `[tasks.migrate]` with `run = "..."`; contributors run `mise run test`. Tasks can declare dependencies and sources/outputs for incremental skipping (Turborepo/Nx-style), and monorepo task references across packages are supported.
- **CI use:** install mise in the runner, `mise install`, then `mise run <task>` - so CI and local execute the IDENTICAL commands and tool versions. Pairs naturally under Dagger too (mise inside the container guarantees the toolchain). Pin the mise version itself in CI.
- **Env discipline:** mise `[env]` is for non-secret config + pointing at the secret source; do NOT put real secrets in committed `mise.toml`. Use it to load a gitignored dotenv or to export the path to the secret manager, not to store credentials.
- **Relationship to Docker/Dagger:** mise manages tools on the HOST/dev machine and lightweight CI; Dagger/Docker manage tools INSIDE containers. They compose - mise for the inner-loop dev ergonomics + simple CI, containers when full isolation/reproducibility is required. Not mutually exclusive.
- **Red flags:** floating/`latest` tool versions in `mise.toml`; secrets committed in `[env]`; using mise to install tools the project then also installs a second way (pick one); shims not activated so the wrong global version silently runs.

---

## Where these sit vs existing references
- `docker-skill.md` - container build + host-clean dev. Dagger generalizes host-clean to the whole pipeline; mise covers the non-container inner loop.
- `terraform-skill.md` - IaC authoring (incl. OpenTofu, already covered). Dagger/mise do not provision infra; mise can pin the Terraform/OpenTofu binary version.
- `gitops-skill.md` - deploy reconciliation. Dagger builds/tests/packages and can trigger deploy; reconciliation stays in GitOps.
- No upstream code is vendored; both tools are host-installed and version-pinned per project; CI invocations remain SHA-pinned per fleet doctrine; no em-dashes.
