# Reddit Voice-of-Customer Tooling (ABSORB)

Absorbed 2026-06-13 from king-of-the-grackles/reddit-research-mcp ("Dialog", MIT, v1.0.0). The VOC methodology in `rules.md` (extraction framework, theme synthesis, watering-hole map) is unchanged - this is the *acquisition + evidence* layer for the Reddit channel specifically, which the methodology previously treated as a manual watering hole. Reddit's own API caps search at 250 results; this tooling is how you research it at scale with receipts.

## Net-new patterns lifted

### 1. Semantic subreddit discovery (beats the 250-result cap)
- Reddit's native search caps at 250 results and only finds subreddits you already name. Use **semantic/vector discovery** over an index of active communities (2k+ members) to surface relevant subreddits you didn't know existed for a given problem space.
- Apply a **confidence threshold** when discovering (e.g. min_confidence ~0.6) so the community set is on-topic, not keyword-adjacent noise.
- This expands the `rules.md` watering-hole map from a fixed list to a per-engagement discovered set.

### 2. Evidence-with-receipts (hard requirement, not a nice-to-have)
- Every VOC finding must link back to the **specific post/comment URL** plus its **upvote count and awards**. "Users complain about X" is not allowed without the receipt. This operationalizes the employee's existing evidence-discipline rule for the Reddit channel: a quote without a linkable, dated source is an assumption.
- Upvotes/awards act as a crude intensity signal - weight a high-upvote pain higher when scoring frequency × intensity (already the synthesis rule).

### 3. Batch multi-subreddit fetch (efficiency)
- Fetch posts across multiple discovered subreddits concurrently rather than one at a time (~70% more efficient per the source). Run discovery → batch-fetch the whole community set → then fetch full comment trees only on the threads that surfaced as relevant. Don't pull every comment tree up front.

### 4. Persistent feeds for ongoing monitoring
- Save a discovered subreddit set as a named **feed** for repeat monitoring instead of re-discovering each cycle. This maps directly onto the standing-intel cadence in `rules.md` (Layer 5): a feed per competitor/segment, reviewed on the monthly tier-1 pass and on triggered events. Persistent feeds turn one-off VOC into a standing listening post.

### 5. Three-layer execution discipline (when wiring any data MCP)
- Generalizable pattern worth keeping: **discover operations → inspect schema (with examples) → execute with validated params.** Inspect the schema before firing a call so parameters are validated up front rather than failing mid-research. Applies to any tool-backed research run, not just Reddit.

## Sampling caveat (carry forward from rules.md)
- Reddit skews technical/skeptical and toward strong-opinion power-users (already noted in `rules.md`). Citations make the bias auditable but do not remove it - triangulate Reddit VOC against G2/Capterra reviews, support tickets, and interviews before concluding. Reddit is one channel, not the verdict.

## CONNECT (host installs - auto-deploy does not install external MCP servers)
- **reddit-research-mcp / "Dialog"** (MIT): hosted MCP at `https://reddit-research-mcp.fastmcp.app/mcp` - no Reddit API credentials needed (server handles auth via Descope OAuth2, public Reddit data only). Add per client: `agent mcp add --scope local --transport http dialog-mcp https://reddit-research-mcp.fastmcp.app/mcp`. The free hosted index covers 20,000+ subreddits; the paid Dialog platform adds chat UI + cross-device feed sync (optional, not required for the MCP).
