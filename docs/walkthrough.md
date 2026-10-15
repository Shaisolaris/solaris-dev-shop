# Narrated walkthrough: find, route and hand off

[Watch or download the 65-second video](https://github.com/Shaisolaris/solaris-dev-shop/releases/download/v0.56/solaris-dev-shop-0.56-walkthrough.mp4)

[English captions (WebVTT)](https://github.com/Shaisolaris/solaris-dev-shop/releases/download/v0.56/solaris-dev-shop-0.56-walkthrough.vtt) · [Media checksums](https://github.com/Shaisolaris/solaris-dev-shop/releases/download/v0.56/MEDIA_SHA256SUMS) · [Observed CLI packets](../examples/walkthrough/observed.json)

This is a narrated command walkthrough using actual output from the published
0.56 wheel and tagged source, captured on October 15, 2026. Commands and output
are paced into scenes; paths are shortened and JSON is excerpted. It is not a
real-time recording or a demonstration of a model performing specialist work.
The router performs no specialist work and makes no model calls.

The MP4 is 2560 by1440, H.264 with AAC audio, about2.4MB. It was decoded in a
browser and checked for layout overflow and non-silent audio. Its SHA256 is
`66f9965c25a3361cd782e9bd23385247e0d91b3bcb27e627cd2ed46d6ae8f23d`.

## Reproduce the source and install

Requires Git and Python3.10+. On macOS or Linux:

```bash
git clone --branch v0.56 --depth 1 https://github.com/Shaisolaris/solaris-dev-shop.git
cd solaris-dev-shop
python3 -m venv .venv
.venv/bin/python -m pip install --no-deps https://github.com/Shaisolaris/solaris-dev-shop/releases/download/v0.56/solaris_dev_shop-0.56-py3-none-any.whl
.venv/bin/solaris-intake self-test
.venv/bin/solaris-intake skills playwright --department quality-security
.venv/bin/solaris-intake intake --explain \
  "Write a test plan for the client portal login regression"
```

The wheel hash is recorded in the release's
[SHA256SUMS](https://github.com/Shaisolaris/solaris-dev-shop/releases/download/v0.56/SHA256SUMS).
It installs the router and catalog, not the employee folders. Keep the checkout
for those. See [installation](install.md) for the Windows route and host notes.
The captured source is commit
`60b97b7b6333a7b6110af82b33da9cddcbed6a5a`.

## Transcript and chapters

### 0:00 · From a task to the right skill

Solaris Dev Shop gives your agent61 specialist skills. Find one and route a task
without a model key.

### 0:07 · Start with the released project

Clone the tagged source and use Python3.10 or newer. Install the router wheel
from the project's GitHub release into an isolated environment. The skills remain
in the checkout.

### 0:19 · Find a skill

Search for Playwright in the quality-security department. The result identifies
the QA Engineer, its summary and actual skill file. Search does not install or
execute it.

### 0:30 · Route one concrete outcome

Ask for a login regression test plan. `--explain` includes routing evidence.
The assignment identifies `solaris.qa-engineer` and its skill path, and records
`performed_work: false`. Routing is not execution.

### 0:43 · An unclear goal needs a question

An unknown goal returns clarification with no assignment. Recognized high-risk
wording triggers human review; lexical matching is not a permission grant.

### 0:52 · Hand off

Open the selected skill in your own agent. Keep companion files and shared
standards available. Supply the task and workspace, then review saved outputs
and checks actually run. The [first-task guide](first-task.md) covers this step.
