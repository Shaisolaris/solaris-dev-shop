# Vector / embedding pipelines for RAG on pgvector - methodology

Depth pass 2026-06-14. Net-new methodology only; NO upstream code bundled. Covers the embedding-ingestion lane the employee never had: generating, loading, backfilling, and re-embedding vectors as a governed pipeline stage, with pgvector as the store. This is the PIPELINE view (E+L+T of embeddings), deliberately scoped away from the DBA's extension/index-administration lane and the backend's API-serving lane.

Citation key (this file): [pgv] pgvector/pgvector PostgreSQL License (OSI-permissive, BSD/MIT-style) ~21k* rel 0.8.x. OSI-permissive, credible, well-starred, active.

Gate-0: data-engineer had ELT/dbt/orchestration/DQ/lakehouse but ZERO vector/embedding/RAG content (grep pgvector|polars|duckdb|vector|embedding|rag -> 0 hits). The DBA already owns pgvector EXTENSION ENABLEMENT + INDEX CHOICE (IVFFlat <1M / HNSW >1M, "pick the index up front"); this file does NOT repeat that - it owns the embedding PIPELINE. Net-new.

Boundary (read first):
- **DBA** owns: enabling the `vector` extension, choosing IVFFlat vs HNSW + index params at scale, table/partition layout, and the at-scale tuning. We consume those decisions; we do not re-decide them.
- **Backend-developer** owns: the query-time RAG API (similarity search endpoint, auth, serving). We feed that table; we do not own the read path.
- **data-analyst / data-scientist** own: retrieval-quality experiment design and result interpretation. We own the pipeline that produces the vectors and the offline recall harness that gates a deploy.
- **This file (data-engineer)** owns: the embedding ELT - chunking, embed-as-a-stage, batch load + upsert, idempotent backfills, incremental re-embedding on content change, model/dimension versioning, and the metric<->index contract between us and the DBA.

---

## 1. Treat embeddings as a derived materialization, not a side effect

- An embedding column/table is a **derived asset** of its source text, exactly like a dbt mart is derived from staging. Apply the same doctrine: it must be **reproducible** (re-runnable from source + a pinned model), **idempotent** (re-running does not duplicate), and **observable** (you can tell what is stale).
- The unit is the **chunk**, not the document. The pipeline's grain is one row per (source_id, chunk_index). Declare and verify that grain like any other table grain (dup/null check on the composite key before first load).
- RAW vs derived split: source text lands in RAW via the normal ingestion ladder (managed connector / CDC / dlt). Chunking + embedding is a TRANSFORM+LOAD step that writes the vector table. Do not embed inside the raw ingest resource - keep E/L and the embed-T separable so you can re-embed without re-ingesting.

## 2. Chunking is a pipeline decision with a contract

- Chunk size and overlap are pipeline parameters, recorded in config and in the row (store `chunk_index`, `token_count`, and the chunking strategy id). They affect recall and cost, so they are not hard-coded magic numbers.
- Defaults to argue from, not blindly apply: token-bounded chunks sized to the embedding model's context and the retrieval need; modest overlap to avoid splitting an answer across a boundary. Structure-aware splitting (by heading/section/code-block) beats blind fixed-size when the source has structure.
- Changing the chunking strategy is a **breaking change to the derived asset** - it requires a full re-embed (see 6), the same way a grain change forces a full-refresh.
- Store enough provenance on each chunk row to reconstruct and to cite: source_id, source_uri/locator, chunk_index, char/token offsets, content hash, created_at.

## 3. Embedding generation as a governed stage

- **Pin the model + dimension.** Record `embedding_model` (name + version) and `dim` per row or per table. The vector column's dimension is fixed by the model; mixing models in one column is invalid - one model per vector column, or a discriminator + separate columns/tables.
- **Batch the API/inference calls.** Embed in batches sized to the provider's limit; this is the materialization-efficiency rule applied to an external call. Respect rate limits with backoff + jitter (same job-retry doctrine as the rest of the pipeline).
- **Make the call idempotent + resumable.** Key work by content hash: if a chunk's hash + model already has a vector, skip it. A failed batch must be resumable (load-package style), never half-writing a document's chunks. This mirrors the dlt load-package / atomic-write rule.
- **Cost + observability.** Embedding calls cost money and time - log token counts and batch latencies, and surface cost per backfill the same way warehouse credits are tracked. A re-embed of a large corpus is a budgeted operation, not a casual rerun.
- **Normalization contract.** If the chosen distance metric needs normalized vectors (cosine via normalized + inner product), normalize at write time and document it; do not leave it implicit between writer and reader.

## 4. Loading + upsert into pgvector

- **Bulk load, never row-by-row.** Stage chunks + vectors and load in batches (COPY / batched INSERT), the same "stage + COPY INTO, no per-row INSERT" floor the rest of the pipeline uses. Row-by-row embedding inserts are a red flag.
- **Upsert on the natural key.** `INSERT ... ON CONFLICT (source_id, chunk_index) DO UPDATE` so a re-run replaces a chunk's vector + content hash + model atomically. The conflict target is the verified grain key.
- **Write metadata alongside the vector** in the same row (tenant_id, source filters, timestamps) so query-time filtering is a WHERE on the same table - filtered vector search needs the filter columns colocated.
- **Index timing.** Building/refreshing the ANN index (HNSW/IVFFlat) is the DBA's call and is expensive - bulk-load first, then (re)build the index, rather than maintaining it row-by-row during a large backfill. Coordinate the index rebuild as a step in the backfill plan.

## 5. The metric <-> index <-> query contract (coordinate with DBA + backend)

- The distance **operator** (`<=>` cosine, `<#>` inner product, `<->` L2) chosen by the read path MUST match the **index opclass** the DBA built (`vector_cosine_ops`, etc.) and the **normalization** the writer applied. A mismatch silently returns wrong neighbors - this is a contract across three owners, so write it down once (in the data contract for the table) and have all three agree, exactly like the RLS-text agreement rule.
- ANN is approximate: recall is traded for speed via index params (HNSW ef_search, IVFFlat probes). The pipeline does not set these (DBA owns it), but the offline recall harness (see 7) is how we PROVE the chosen params meet the retrieval SLA before sign-off.

## 6. Incremental re-embedding on content change

- **Change detection by content hash.** Store a content hash per chunk. On each run, only chunks whose source text changed (hash differs) or are new get re-embedded; unchanged chunks are skipped. This is the watermark/CDC discipline applied to embeddings - process the delta, not the world.
- **Deletes + tombstones.** When a source document or chunk disappears, its vectors must be removed (or tombstoned) so retrieval cannot surface stale content. Reconcile deletions explicitly; an append-only embed pipeline that never deletes is a correctness bug for RAG.
- **Model upgrade = full re-embed, versioned.** A new embedding model is a breaking change to the whole column. Do it as a versioned backfill: write the new vectors into a new column/table tagged with the new model+dim, validate recall on the new vectors, then cut the read path over - never silently overwrite live vectors mid-flight. Keep the old vectors until the new ones are validated (expand-and-contract for embeddings).
- **Backfills are partitioned + resumable** like any other backfill - per source-batch or per logical partition, with progress tracked so a failure resumes instead of restarting the whole corpus.

## 7. Quality gate: offline recall before deploy

- A retrieval pipeline ships behind a **gold-set recall check**, the embeddings analogue of dbt tests / DQ gates: a fixed set of (query -> expected relevant chunk) pairs, and a metric (recall@k / hit-rate) that must clear a threshold to pass. A re-embed or model swap that drops recall below the bar fails the deploy.
- Also gate the mechanical invariants as run-failing checks: no null/zero vectors, dimension == declared dim for every row, no orphan vectors whose source was deleted, no duplicate (source_id, chunk_index). These are cheap DQ assertions on the vector table.
- Freshness SLA applies: declare how stale the index may be relative to source (e.g. re-embed lag warn/error), the same freshness contract used on any source.

## 8. Hosting + scope notes
- pgvector is a Postgres extension; the DBA/host enables it (`CREATE EXTENSION vector`) and owns index strategy. We do not bundle or fork it - methodology only; the engine is installed by the host.
- When the corpus or QPS outgrows pgvector's ANN, escalate the store choice (dedicated vector DB) to the DBA + backend as an architecture decision; the pipeline doctrine above (chunk grain, hash-incremental, versioned re-embed, recall gate) is store-agnostic and carries over.
