# Claude Context - Semantic Code Search Operator

> ⚠️ ALWAYS load this file FIRST when reviewing or auditing a codebase larger than ~2,000 files (CTT, Turnpike, Kellbell, any inherited project takeover). Without semantic indexing, audits fall back to grep - which misses everything that doesn't match exact strings.

**Source canon:** [zilliztech/claude-context](https://github.com/zilliztech/claude-context) - 9,797 stars, MIT, last commit 2026-04-27. Code-search MCP for Claude Code that turns the entire codebase into the agent's context via vector embeddings + Merkle-tree incremental indexing + Milvus / Voyage / OpenAI / Gemini embeddings.

This is the missing capability for Code Reviewer. The base 6-mode review skill (PR Review / Full Audit / Security Audit / Dependency Audit / First-Principles / Adversarial / Debug) has always assumed Claude can navigate a codebase. On large client codebases, that assumption breaks - grep finds exact strings; semantic search finds intent.

---

## When to use claude-context vs raw grep

| Scenario | Use |
|----------|-----|
| File is open / known location | Read tool directly - don't index for trivial work |
| Project < 500 files | Grep is fine; indexing overhead exceeds benefit |
| Project 500-2,000 files, exact symbol search | Grep first, claude-context if grep misses |
| Project > 2,000 files OR semantic queries | claude-context **mandatory** - index on session start |
| "Find all functions that look like X" (intent) | claude-context - grep can't do semantic |
| "Find every input that flows to a SQL query" (taint analysis lite) | claude-context + grep combined |
| Inherited codebase audit (Phase 1 of Full Audit mode) | claude-context **mandatory** - orientation step |
| Security audit on legacy codebase | claude-context for surface enumeration + grep for exact pattern verification |
| Performance audit (find all DB query call sites) | claude-context for "any code that does database access" |

---

## Install

```bash
# MCP install - preferred
claude mcp add claude-context -- npx -y @zilliz/claude-context-mcp

# Provide embedding provider key (one of)
export VOYAGE_API_KEY=...      # Anthropic-recommended for accuracy
export OPENAI_API_KEY=...      # text-embedding-3-large or 3-small
export GOOGLE_API_KEY=...      # Gemini embeddings
# Or use local ollama for embeddings (free but slower indexing):
export OLLAMA_BASE_URL=http://localhost:11434

# Vector storage
# Default: Milvus (zilliztech's own; managed Zilliz Cloud free tier or self-host)
# Alternative: Qdrant, pgvector
```

**Embedding provider decision rule:**
- **Voyage** - best retrieval accuracy for code; ~$0.12 per million tokens
- **OpenAI text-embedding-3-large** - second-best accuracy; widely available
- **OpenAI text-embedding-3-small** - cheap; good enough for most reviews
- **Ollama (local)** - free, zero data leaves machine; use for client codebases under NDA where embedding-API providers are not approved

For client work with sensitive code: Ollama + local Milvus or local Qdrant. Period.

---

## Standard workflow - first index of a new codebase

1. **Open the project in Claude Code.**
2. **Index it once at session start:**
   ```
   /index_codebase
   ```
   First index takes 5-30 min depending on size + embedding provider. Subsequent sessions use Merkle-tree to detect changed files and re-embed only those - typically < 30 sec.
3. **Verify the index:**
   ```
   /search_code "authentication middleware"
   ```
   Should return relevant files with relevance scores. If results look wrong, the index didn't take - re-run.
4. **Now run the audit / PR review / debug session.** Claude can call `search_code` autonomously when it needs to find code by intent rather than by string.

---

## Workflow patterns by mode

### Mode: Full Audit (codebase handoff)
The 7-phase / 20-angle protocol assumes orientation. Claude-context is the orientation tool:
- **Phase 1 - Orientation:** semantic queries to map architecture. "Where is the data layer?" "Where is the auth boundary?" "What integrations exist?" "Where are the third-party API call sites?"
- **Phase 3 - Security:** "Find every input that flows from request to query." "Find every place secrets are read." "Find every place auth is checked OR skipped."
- **Phase 5 - Performance:** "Find every database query." "Find every loop that calls a function - N+1 candidate." "Find every cache invalidation site."

### Mode: PR Review
- For diffs touching unfamiliar areas: query "what other code uses this function" - grep can do this for exact names; claude-context catches semantic call-sites (e.g. adapters, facades, dynamic dispatch)
- For new feature PRs: query "where does this category of behavior already exist" - find duplications before they're committed

### Mode: Debug
- Bug report: "users can't reset password" → semantic query "password reset" → enumerate every relevant file → narrow to call site → reproduce
- Symptom only: "intermittent 500 in production" → query relevant area + recent commits + surrounding error handling

### Mode: Security Audit
- Surface enumeration: "Find every endpoint that takes user input" → enumerate → review each for auth + validation + escape
- Specific threat: "Find every place where shell commands are constructed" → manual review for injection
- Auth flow trace: "Find every function that issues a session token OR validates one" → verify single source of truth

### Mode: Dependency Audit
- claude-context isn't the right tool here - `npm audit` / `composer audit` / `pip-audit` etc. are. Use base 6-mode protocol.

---

## Decision rules

- **Index on session start** for any project > 2,000 files
- **Re-index on session start** if days have passed since last session - Merkle-tree handles incremental
- **Don't trust the index blindly** - verify a sample query returns sensible results before relying on it
- **Combine semantic + grep** - semantic finds candidates; grep verifies exact occurrences
- **For NDA / sensitive code** - Ollama + local Milvus only; never send embeddings to a cloud API the client hasn't approved
- **Cache embeddings per-project** - claude-context handles this; don't wipe the project DB unless the codebase fundamentally changed
- **Document the index location** in the per-project `RUNBOOK.md` so future sessions don't re-discover

---

## Anti-patterns

- ❌ **Using semantic search for trivial tasks** - if grep would work, use grep; semantic search has latency + cost
- ❌ **Skipping verification of search results** - semantic search returns relevant ≠ correct; always confirm specific findings
- ❌ **Sending NDA code to cloud embedding APIs without approval** - use Ollama or get explicit client OK
- ❌ **Indexing a fresh-cloned monorepo without a `.gitignore`-style exclude** - `node_modules`, `vendor/`, build artifacts, generated code all bloat the index uselessly
- ❌ **Trusting the semantic answer for security-critical claims** - semantic search is a *finder*, not a *prover*. For "is there ANY place this auth check is skipped" the answer needs grep verification
- ❌ **Re-indexing the same codebase 5x in one session** - Merkle-tree handles incremental, but the "is it indexed" check has cost; index once at start

---

## Cross-references inside Solaris

- **CTO** - Phase 1 of the project takeover protocol gains a concrete first step: "index the inherited codebase with claude-context before doing anything else"
- **Full-Stack Developer** - same install pattern works for navigation during dev work, not just review
- **Security Auditor** - surface enumeration is the dominant first step of any audit; this is the tool
- **Performance Engineer** - N+1 queries and unindexed-DB-call enumeration become tractable on large codebases
- **DevOps Engineer** - for ClaudeBox per-project containers, install claude-context inside the container so embeddings never leak across clients

---

## What this does NOT do (for completeness)

- ❌ Doesn't *replace* grep - it complements it
- ❌ Doesn't *replace* the LLM's own code reading - it points the LLM to relevant code
- ❌ Doesn't *replace* dependency CVE scanning - that's still `npm audit` / friends
- ❌ Doesn't *replace* AST-based static analysis - semgrep / CodeQL / Snyk Code still own that

---

## Optional: pairing with other tools

- **Pair with `tree-sitter` based AST search** when needed (claude-context is embedding-based; semgrep is AST-based - they catch different things)
- **Pair with GitHub MCP server** - repo-level metadata (PR history, author blame, issue links) augments semantic findings
- **Pair with Sentry MCP** - connect production error fingerprints to semantic-relevant code paths
