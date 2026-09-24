# ML Engineering Stack - fine-tune, evaluate, track, serve (methodology)

Distilled methodology for the four hot paths that the SKILL names but never operationalized: fine-tuning, model evaluation (for generative/fine-tuned models), experiment tracking, and serving. All sources are Apache-2.0 and host-installed - nothing is vendored here. This file is the "how", the SKILL is the "when". Verified 2026-06-13.

Loop these in order: fine-tune -> evaluate -> track -> serve.

---

## 1. Fine-tuning recipe (Unsloth + Axolotl)

Sources: unslothai/unsloth (Apache-2.0, 66k stars) for speed; axolotl-ai-cloud/axolotl (Apache-2.0, 12k stars) for config discipline. Self-host: both are pip-installed in the training env; pick one per job, do not stack.

Reach for this ONLY after the 4-question decision tree (rules.md) says fine-tune. Default to LoRA/QLoRA, never full fine-tune, unless eval proves the adapter is insufficient.

### Defaults that work
- **QLoRA first.** Load the base in 4-bit (nf4), train rank-16 / alpha-16 adapters on attention + MLP projection modules. This is ~95% of full-fine-tune quality at a fraction of the VRAM, and a 70B QLoRA fits on a single 24GB GPU.
- **Rank/alpha:** start rank 16, alpha 16 (alpha = rank is a safe default). Bump rank to 32-64 only if eval shows underfitting. Higher rank = more capacity + more VRAM + more overfit risk.
- **Sequence packing** on for short examples (big throughput win); off when example boundaries matter semantically.
- **LR + schedule:** 2e-4 for LoRA, cosine schedule with ~3% warmup. Lower (1e-4) if loss is unstable.
- **Gradient checkpointing** on by default - trades compute for memory, the usual right call on one GPU.
- **Export:** merged-16bit for serving via vLLM/Transformers, or GGUF for llama.cpp/CPU. Keep the raw adapter too - it is tiny and lets you hot-swap (see serving).

### Config-as-spec discipline (from Axolotl)
- The entire run is ONE YAML/config file: base model, dataset path + format, LoRA vs QLoRA vs full, packing, eval split, epochs, LR, output dir. The config IS the experiment record.
- Diff configs between runs the way you diff code. A run you cannot reproduce from a committed config did not happen.
- Commit the config alongside the eval results and the MLflow run id (see section 3).

### Hard rules
- Always carve a held-out eval split BEFORE training and never let it touch the optimizer.
- Speed kernels (Unsloth) change numerics slightly - re-run the eval harness, do not assume parity with a vanilla run.
- Watch the base-model license (many Hub models are non-commercial / gated). Permissive training tooling does NOT make a gated base commercially safe.

---

## 2. Evaluation harness for generative / fine-tuned models (DeepEval)

Source: confident-ai/deepeval (Apache-2.0, 16k stars). Self-host: pip-installed; LLM-as-judge metrics call out to a judge model (configurable, including local) - budget for that cost/latency. This fills SKILL's "eval harness before/after fine-tune" promise. Classical metrics (F1, ROC-AUC, MAE) still live in the SKILL eval section; this is specifically for free-text / generative output where there is no single right answer.

### The discipline
- **Eval is a test suite, not a vibe check.** Write eval cases the same way you write pytest: a dataset of inputs + expected behavior + per-metric pass/fail thresholds. CI runs them; a regression fails the build.
- **Before AND after.** Baseline the un-tuned model on the eval set first. The fine-tune only earns its keep if it beats that baseline on the metrics that matter, without regressing others.
- **Pick metrics for the task, not all of them:**
 - Faithfulness / hallucination - does the output stay grounded in the provided context?
 - Answer relevancy - does it actually address the input?
 - G-Eval (LLM-as-judge with a written rubric) - for bespoke quality criteria (tone, format, correctness) that no off-the-shelf metric captures. Write the rubric explicitly.
 - Task completion - for agentic / multi-step outputs.
- **Thresholds are contracts.** Set a numeric pass bar per metric (e.g. faithfulness >= 0.8). Below it = fail = do not ship.
- **LLM-as-judge caveats:** the judge is itself a model - pin its version, keep the rubric in version control, and spot-check judge calls against human labels before trusting it at scale.

### When NOT to use this
Pure classification/regression/forecasting → use the classical metrics in the SKILL. This harness is for generative text where exact-match scoring is meaningless.

---

## 3. Experiment tracking + model registry (MLflow)

Source: mlflow/mlflow (Apache-2.0, 26k stars). Self-host: run the tracking server locally or point at a managed backend; artifacts go to a file store or S3.

### Tracking discipline
- **Autolog from line one.** Turn on autologging so params, metrics, and artifacts are captured without manual `log_*` calls everywhere. Every training run becomes a comparable, queryable record.
- **One run = one experiment attempt.** Log the config (section 1), the eval results (section 2), git SHA, dataset version/hash, and the trained artifact. A run you cannot trace back to its exact inputs is noise.
- **Log a model signature** (input/output schema) with the artifact so serving has a contract to validate against.

### Registry promotion flow
- Register the artifact as a named model with versions: `v1`, `v2`, ...
- Promote through stages: None -> Staging -> Production -> Archived. Promotion is a deliberate, logged decision tied to passing the eval harness, not an overwrite.
- Production serving (section 4) pulls "the Production-stage version of model X" - never a hardcoded file path. Rollback = re-point the stage, no redeploy.

This is the concrete answer to the SKILL's "experiment tracking" + "model registry" bullets and the long-missing `mlops-pipeline.md` reference.

---

## 4. Serving fine-tuned models (vLLM)

Source: vllm-project/vllm (Apache-2.0, 82k stars). CONNECT + self-host: vLLM is the inference runtime, host/infra-installed. The K8s, autoscaling, and GPU provisioning around it belong to DevOps + Cloud Architect (per the SKILL hand-off table) - this employee owns the model + the serving contract, not the cluster.

### Decision: how to serve
- **Classical / small models (sklearn, XGBoost, a small torch net):** FastAPI + ONNX/TorchScript. vLLM is overkill. (This path already implied in the SKILL.)
- **LLM / large generative models, throughput matters:** vLLM. PagedAttention + continuous batching give far higher tokens/sec and GPU utilization than naive Transformers `generate`.
- **Many fine-tunes off one base:** serve LoRA adapters with vLLM's multi-adapter hot-swap - one base model in VRAM, swap adapters per request. Far cheaper than one full model per fine-tune. This is the payoff for keeping raw adapters in section 1.

### Serving contract (what this employee hands off)
- OpenAI-compatible endpoint (vLLM exposes one) so clients are model-agnostic.
- The model signature from the registry (section 3) is the request/response schema.
- A latency budget (P95/P99) and a fallback when the model is unavailable - agreed with backend-developer.
- Verify export parity: ONNX/TorchScript/quantized export can silently change outputs - run the eval harness (section 2) against the SERVED endpoint, not just the training checkpoint.

### Hard rule
Do not own the cluster. Provide the model, the serving config, the contract, and the eval-on-served-endpoint proof; hand GPU infra + autoscaling to DevOps.
