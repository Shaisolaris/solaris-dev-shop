# Performance forensics: differential flamegraph reading, CWV field-to-lab attribution, and the N+1 EXPLAIN loop

> Methodology reference. NO tool code bundled. This is the INVESTIGATIVE READING discipline - what to do with a profile, a CWV report, or a slow query once you have it. It is distinct from the existing files, which provide the TOOLS and the continuous monitoring; this file is the ad-hoc forensic reasoning that finds the actual root cause and proves it.

Gate-0 (what the cluster already had, so this is NET-NEW depth, not a re-list):
- perf-observability-patterns.md = the TOOLS: Pyroscope (continuous profiling + flamegraph diff between deploys), Unlighthouse (site-wide CWV crawl + CI budget gate, lab + CrUX field), pgBadger (Postgres slow-log aggregation), OTel/Locust. It names flamegraph-diff, CWV field+lab, and EXPLAIN, but as monitoring/gating tooling.
- k6-load-test-patterns.md = load generation + threshold gates.
- rules.md = profile-before-optimize golden rule, the EXPLAIN-first and N+1-eager-load decision rules, CWV targets, the static perf-risk checklist.
NONE carried: (1) HOW to READ a differential flamegraph and the on-CPU vs off-CPU distinction that decides which profiler to even use, (2) the INP field-to-lab attribution chain that turns "users feel slow" into a specific main-thread cause, (3) the N+1-to-EXPLAIN forensic loop with the BUFFERS/row-estimate read. All three NET-NEW.

---

## 1. Flamegraph forensics - reading, not just diffing

The tools give a flamegraph; the skill is reading it. Two distinct failures need two distinct profiles, and using the wrong one is the most common forensic mistake.

### On-CPU vs off-CPU - decide before you profile
- **On-CPU profiling** (the default sampling profiler, what Pyroscope/perf give) answers "where is the CPU burning cycles." Width = samples = CPU time spent in that stack. Use it when the box is CPU-bound: high CPU%, compute-heavy work, hot loops, serialization, regex, crypto.
- **Off-CPU profiling** answers "where is the thread BLOCKED and not running" - waiting on a lock, a disk read, a downstream HTTP/DB call, a channel. A request that is slow but the CPU is idle is an off-CPU problem, and an on-CPU flamegraph will look empty exactly where the latency lives. This is the blind spot: most "the service is slow but CPU is low" investigations fail because someone read an on-CPU graph and saw nothing.
- Forensic rule: if wall-clock latency is high but CPU utilization is low, the time is off-CPU (waiting). Reach for off-CPU profiling / wait analysis / the distributed trace (OTel spans, perf-observability-patterns.md), not the on-CPU flamegraph.

### Reading a flamegraph (single)
- Width is time/samples, NOT call order; x-axis is alphabetical-merged frames, not a timeline. Do not read it left-to-right as execution order.
- Find the widest PLATEAUS at the top (leaf frames) - those are where time is actually spent, not the tall towers (deep call stacks are normal). A wide leaf you did not expect is the bottleneck.
- Watch sampling resolution (rules.md): the sample rate must out-resolve the hot function's call frequency or a real hot path hides in the noise.

### Differential flamegraph forensics (the regression hunt)
perf-observability-patterns.md diffs two deploys; this is how to READ that diff to assign blame.
- A differential flamegraph colors frames by DELTA (got wider = regressed, got narrower = improved) between baseline and current. The forensic question is "which frame grew, and is the growth in OUR code or a dependency's."
- Establish the baseline from a known-good window/version (the before/after measurement template, rules.md). Diff like-for-like: same endpoint label, same load shape (correlate with the k6/Locust window), same input distribution - a diff across different traffic mixes is noise, not signal.
- A frame that grew but whose CALLERS did not is a local regression (that function got slower). A frame that grew because it is CALLED MORE (a new N+1, a retry storm) is a call-count regression - the fix is upstream, not in the hot function. Distinguish the two before optimizing: making a function called 10,000x-too-often faster is the wrong fix.
- Confirm with a re-measure after the fix (golden rule): the differential should flatten on the previously-red frame, with no new red frame introduced (a fix-introduced regression, the perf analog of the code-reviewer fix-introduced-bug check).

---

## 2. Core Web Vitals forensics - field-to-lab attribution (INP-first)

perf-observability-patterns.md gates CWV in CI (lab budgets + CrUX field). Forensics is the attribution chain that turns a failing field metric into a specific, fixable cause. INP is the priority: it is the most-failed CWV in 2026 and it CANNOT be measured in the lab.

### Why field AND lab, never one alone
- **Field (CrUX / RUM)** is ground truth - real users, real devices, real networks, 75th percentile. It tells you a problem EXISTS and for whom. INP only exists in the field because it needs real interactions; lab tools report Total Blocking Time (TBT) as a proxy, and TBT does not correlate perfectly with INP.
- **Lab (Lighthouse / DevTools / Unlighthouse)** is reproducible - it tells you WHY, under controlled conditions, and lets you iterate a fix. But a good lab score with a bad field score is a real and common state (the lab device is faster than the user's).
- Forensic rule: start from the field metric that fails at p75, then reproduce in the lab under a matching throttle (CPU 4x-6x slowdown, slow 4G) until the lab reproduces the field pain. Optimizing against an unthrottled lab that already passes is optimizing the wrong thing.

### The per-metric attribution chain
- **INP (responsiveness, target <200ms p75):** an interaction has three phases - input delay (main thread busy when the user clicks), processing time (the event handler), presentation delay (rendering the next frame). Record the interaction in the DevTools Performance panel and read the main-thread flame chart for the slow interaction: a long task BEFORE the handler = input delay (split/defer that work, yield to the main thread); a long handler = processing (debounce, move work off the main thread / to a worker, break long tasks with scheduler.yield); a long paint = presentation (reduce DOM size / layout cost). Map the worst real-user interaction (from RUM) to its handler, do not guess.
- **LCP (loading, <2.5s):** decompose into TTFB + resource load delay + resource load time + render delay. The LCP element is usually one image or text block - find it, then attribute: slow TTFB (server/CDN, correlate with the backend profile and pgBadger), late discovery (preload/fetchpriority), or render-blocking CSS/JS.
- **CLS (visual stability, <0.1):** find the shifting element in the DevTools Layout Shift regions - almost always an image/ad/embed without reserved dimensions or a late-injected element.

### Amdahl targeting (reuse the existing rule)
Fix the worst template first: the worst-LCP/INP page template usually repeats across thousands of URLs (perf-observability-patterns.md), so one template fix moves the whole site's p75. Triage by population x severity, not by single worst URL.

---

## 3. The N+1 to EXPLAIN forensic loop (DB latency)

rules.md says "EXPLAIN first" and "fix N+1 by eager loading"; pgBadger aggregates the slow log. This is the forensic loop that connects detection to proof to fix.

### Detect the N+1 (count, do not eyeball)
- The signature is many near-identical queries differing only in a bound id, one per row of a parent result. Detect by counting queries-per-request (rules.md checklist: "count queries/req"), via the ORM query log, an OTel DB-span count on one trace, or pgBadger's normalized-fingerprint frequency (a fingerprint executed N times where N tracks row count). A fast query run 1,000x beats a slow query run twice - total time, not per-call time, is the target (pgBadger top-by-total-time).
- Confirm it is N+1 and not legitimate volume: the tell is that the count scales with parent rows. Fix by eager/batch load (JOIN or a single `WHERE id IN (...)`), never by caching the symptom (rules.md).

### Prove the plan with EXPLAIN (ANALYZE, BUFFERS)
- Run `EXPLAIN (ANALYZE, BUFFERS)` - ANALYZE actually executes and gives real timing + row counts; BUFFERS shows the I/O. Plan-only EXPLAIN gives the planner's guess, not reality.
- Forensic reads:
  - **Seq Scan on a large table** in a hot path = a likely missing index (but add deliberately - over-indexing kills writes, rules.md).
  - **Estimated rows vs actual rows wildly diverging** = stale statistics (ANALYZE the table) or a bad plan; the planner is choosing the wrong strategy because its estimate is wrong. This is the single most-missed DB forensic signal - the index exists but is not used because the estimate is off.
  - **High Buffers / shared read** = the query is going to disk, not cache - either a working-set/memory problem or a scan that should be an index lookup.
  - **Nested Loop with a high outer row count** = the join is effectively an N+1 inside the database; consider a hash/merge join via a rewrite.
- Loop: detect -> EXPLAIN ANALYZE to confirm the plan and the cause -> apply ONE change (index, rewrite, eager load) -> re-EXPLAIN and re-measure end-to-end latency (golden rule) -> confirm the plan changed AND the p95 dropped, with no write-path regression. Hand deep schema/index work to the DBA (existing hand-off rule).

---

## Cross-references
- references/perf-observability-patterns.md - the TOOLS this file reads: Pyroscope produces the flamegraphs (section 1), Unlighthouse + CrUX produce the CWV field/lab data (section 2), pgBadger produces the slow-query fingerprints (section 3), OTel spans give the off-CPU/distributed view. NO tool list duplicated here.
- references/k6-load-test-patterns.md - load shape to correlate with the flamegraph window so a differential diff is like-for-like.
- rules.md - profile-before-optimize golden rule, before/after measurement template, EXPLAIN-first + N+1 + CWV-target + sampling-resolution decision rules this file operationalizes; the static perf-risk checklist feeds the N+1 detection.
- DBA hand-off - deep index/schema/plan work after the forensic loop confirms the cause (existing hand-off rule).
- code-reviewer references/variant-analysis-and-fix-verification.md - the fix-introduced-regression check in section 1 is the perf analog of the fix-introduced-bug discipline; a perf fix that creates a new red frame is a partial fix.

## Memory scope keys
- performance-engineer/<project>/baseline - the known-good profile + CWV p75 + query plan + p95 latency baseline that every differential and every re-measure is compared against
- performance-engineer/<project>/regressions/<finding-id> - the confirmed bottleneck (flamegraph frame / INP interaction / query fingerprint) + root cause (local vs call-count vs plan) + the proof (before/after measure), so a later regression on the same path is recognized fast
