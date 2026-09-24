# RAG Architecture Patterns

Retrieval-Augmented Generation is the most common production AI/ML pattern in 2026. Reference for client engagements.

## When to use RAG vs alternatives
- **RAG** - when answers must cite specific documents / knowledge bases that change over time. Customer support, internal search, compliance assistants.
- **Fine-tuning** - when you need consistent style/tone/format that prompts can't reliably hit. Rare; usually a last resort.
- **Just prompting** - when the model already knows the domain and there's no proprietary content to inject. Most general-knowledge use cases.
- **Agents (tool-using)** - when the AI needs to take actions (write to DB, call APIs, run code), not just retrieve facts.

Most "we need AI" client briefs are actually RAG.

## The 5 production-quality steps
### 1. Chunking
- **Default: 500-1000 token chunks with 50-100 token overlap**
- **By section, not by character count** - split on headings / paragraphs where possible
- **Preserve metadata** - source URL, section, last-updated date, author
- For code: split by function/class, not by line count

### 2. Embedding
- **Default: OpenAI text-embedding-3-large** for quality, **text-embedding-3-small** for cost
- **Open-weight: BGE-large or E5-large** if cost or sovereignty matters
- **Match embedding model at index + query time** - never switch mid-system

### 3. Vector store
- **pgvector** for < 1M vectors and a Postgres-already-in-place stack
- **Pinecone / Weaviate / Qdrant** for managed, larger scale
- **Milvus / Chroma** for self-hosted
- **Index type: HNSW** for most cases; **IVF** for very large + cold

### 4. Retrieval
- **Hybrid search (BM25 + vector)** beats pure-vector almost always
- **Re-rank top 20 → top 5** with a cross-encoder (Cohere Rerank or BGE-reranker)
- **Filter on metadata first**, then semantic - narrow the search space
- **MMR (Maximal Marginal Relevance)** for diversity in retrieved chunks

### 5. Generation
- **Stuff retrieved chunks into prompt with explicit instructions** to cite source
- **Cite every claim** with chunk ID/source
- **Refuse-when-uncertain** prompt: "If the retrieved context doesn't answer, say 'I don't have that information.'"
- **Stream the response** for UX

## Quality measurement
- **Retrieval quality** - was the right chunk in top-5? Manual eval first, then automated.
- **Generation quality** - answer correctness, citation accuracy, refusal-when-appropriate rate
- **Latency budget** - typical: 50ms retrieval + 800ms LLM = 850ms p50

## Anti-patterns
- Chunking by character count without section awareness - context gets sliced
- Pure vector search without hybrid - recall suffers on out-of-vocab queries
- Stuffing 50 chunks into context - model gets lost; rerank to 5
- Not citing sources - user can't verify, trust collapses
- No "I don't know" - model hallucinates rather than refuse

## Tooling stacks
- **LangChain** - most popular, lots of integrations, can be heavy
- **LlamaIndex** - RAG-first, cleaner abstractions
- **Haystack** - production-focused, German team
- **DIY** - for small/simple, often best (no framework lock-in)

## Cost benchmarks (2026)
- text-embedding-3-large: ~$0.13/M tokens
- text-embedding-3-small: ~$0.02/M tokens
- pgvector self-hosted: $0 (your Postgres cost)
- Pinecone Standard: ~$70/mo for 5M vectors
- LLM cost dominates (~95% of total) - choose Sonnet/Haiku for production unless quality demands Opus
