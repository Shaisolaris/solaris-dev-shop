# AI/ML Engineer - Top-5 Verified Source Candidates (2026)

Depth pass, dated 2026-06-13. Goal: strengthen ML engineering across training / fine-tuning, evaluation, serving / inference, and experiment tracking. Each candidate is established, actively maintained, permissively licensed, and Gate-0 checked against the employee's ACTUAL current content (`SKILL.md`, `rules.md`, `learnings.md`, `references/`).

Gate-0 method: grep the live files for the candidate's core concepts. "Content-duplicate" = the methodology already lives here. "Net-new / thin" = named in passing but no operational methodology, so it is safe to deepen.

---

## 1. Unsloth - fast, memory-efficient LoRA/QLoRA fine-tuning

- **URL:** https://github.com/unslothai/unsloth
- **Stars:** 66,432
- **License:** Apache-2.0 (permissive)
- **Last commit:** 2026-06-13 (active daily)
- **Maintainer:** unslothai (organization, https://unsloth.ai)
- **What it adds:** Concrete, reproducible fine-tuning recipes. Custom Triton kernels give roughly 2x speed and ~70% less VRAM, so a 70B QLoRA fits on a single 24GB GPU. Turns the employee's abstract "LoRA/QLoRA" mentions into an actual default training path: 4-bit base load, rank/alpha/target-module defaults, gradient checkpointing, export to GGUF/merged-16bit.
- **Gate-0 verdict:** LoRA/QLoRA appear 29x but ONLY as decision-tree concepts ("when NOT to fine-tune"). Zero training recipe, zero VRAM/speed methodology, zero export path. NOT content-duplicate - thin mention only.
- **Tag:** METHODOLOGY (lift recipe defaults; do not vendor kernels)

## 2. Axolotl - config-driven (YAML) fine-tuning pipeline

- **URL:** https://github.com/axolotl-ai-cloud/axolotl
- **Stars:** 12,045
- **License:** Apache-2.0 (permissive)
- **Last commit:** 2026-06-12 (active)
- **Maintainer:** axolotl-ai-cloud (organization, https://docs.axolotl.ai)
- **What it adds:** The reproducible, declarative side of fine-tuning. One YAML file fully specifies base model, dataset format, LoRA vs full vs QLoRA, sequence packing, eval split, and run config. This is the "experiment is a file you can diff and re-run" discipline the employee preaches for classical ML but never extended to fine-tuning. Pairs with Unsloth (speed) as the config layer.
- **Gate-0 verdict:** Zero hits for "axolotl", "yaml train", "config-driven". Net-new.
- **Tag:** METHODOLOGY (lift the config-as-spec discipline)

## 3. DeepEval - LLM / fine-tune evaluation harness (pytest-style)

- **URL:** https://github.com/confident-ai/deepeval
- **Stars:** 16,140
- **License:** Apache-2.0 (permissive)
- **Last commit:** 2026-06-13 (active daily)
- **Maintainer:** confident-ai (organization, https://deepeval.com)
- **What it adds:** A regression-test framework for model outputs. 50+ metrics (G-Eval / LLM-as-judge, faithfulness, answer relevancy, hallucination, task completion), pytest integration with per-metric pass/fail thresholds, and dataset-based eval. The employee's eval section is classical-only (F1, ROC-AUC, MAE). It has NO methodology for evaluating a fine-tuned generative model - exactly the gap that blocks the "eval harness before/after fine-tune" step it already promises.
- **Gate-0 verdict:** Zero hits for "deepeval", "g-eval", "llm-as-judge". SKILL.md promises "Eval harness - before fine-tune, after fine-tune, regression checks" with no method behind it. Net-new - fills a promised-but-empty capability.
- **Tag:** METHODOLOGY (lift the eval-harness discipline; pytest assertion pattern)

## 4. MLflow - experiment tracking + model registry methodology

- **URL:** https://github.com/mlflow/mlflow
- **Stars:** 26,500
- **License:** Apache-2.0 (permissive)
- **Last commit:** 2026-06-13 (active daily)
- **Maintainer:** mlflow (organization, https://mlflow.org)
- **What it adds:** The operational backbone the MLOps section names but never explains. Autolog params/metrics/artifacts, the run -> registered-model -> stage (Staging/Production) promotion flow, model signatures, and reproducible packaging. Converts "Experiment tracking: MLflow, W&B, Neptune" from a tool list into a how-to-actually-track-experiments methodology.
- **Gate-0 verdict:** "MLflow" named 2x (tool list + registry list) with zero methodology. NOT content-duplicate - list mention only.
- **Tag:** METHODOLOGY (lift the tracking + registry promotion flow)

## 5. vLLM - high-throughput LLM serving / inference engine

- **URL:** https://github.com/vllm-project/vllm
- **Stars:** 82,772
- **License:** Apache-2.0 (permissive)
- **Last commit:** 2026-06-13 (active daily)
- **Maintainer:** vllm-project (organization, https://vllm.ai)
- **What it adds:** The serving layer for fine-tuned models. PagedAttention, continuous batching, OpenAI-compatible server, and LoRA-adapter hot-swap so multiple fine-tunes share one base. The employee lists "Serving: ... BentoML; Triton" but has no inference methodology and nothing on serving the LoRA adapters it just fine-tuned. Closes the loop: fine-tune (1,2) -> evaluate (3) -> track (4) -> serve (5).
- **Gate-0 verdict:** "BentoML"/"Triton" named once in a serving list; "vllm" zero hits; no inference methodology anywhere. NOT content-duplicate.
- **Tag:** METHODOLOGY + CONNECT note (serving runtime is host-installed / infra-owned; lift the when-to-use + adapter-serving decision methodology, hand K8s/GPU infra to DevOps)

---

## Honorable mentions (verified, not in top-5)

- **RAGAS** (https://github.com/vibrantlabsai/ragas) - 14,355 stars, Apache-2.0, last commit 2026-02-24. Strong RAG-specific eval metrics (faithfulness, context precision/recall). Excluded from top-5 because RAG-system building is explicitly routed to LLM Agent Designer; DeepEval covers the fine-tune-eval gap that is in-scope here without the scope collision. Worth a cross-reference in LLM Agent Designer instead.
- **LLaMA-Factory** (https://github.com/hiyouga/LlamaFactory) - 72,134 stars, Apache-2.0, last commit 2026-06-13. Unified fine-tuning for 100+ models. Overlaps Unsloth + Axolotl; kept as a fallback rather than a third fine-tuning entry.
- **HuggingFace PEFT** (https://github.com/huggingface/peft) - 21,268 stars, Apache-2.0. The foundation LoRA library; already implicitly covered via the existing HuggingFace Transformers usage and the HF MCP connection.

All five top candidates are Apache-2.0 (permissive, commercial-safe). No GPL / AGPL / NOASSERTION flags. Tools are NOT vendored - methodology is distilled and runtimes are host-installed.
