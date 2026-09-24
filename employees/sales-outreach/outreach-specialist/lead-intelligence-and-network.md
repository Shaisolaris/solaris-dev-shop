# Lead Intelligence (AI-native scoring) + Network Growth / Warm Paths

Last revised: 2026-06-14
Absorbed from (methodology only, no code bundled): affaan-m/ECC (MIT) skills `lead-intelligence` (+ agents signal-scorer, mutual-mapper, enrichment-agent, outreach-drafter) and `connections-optimizer`.

**Why this file exists.** The base prospecting motion (rules.md, SKILL.md) is tool-centric: Apollo/Clay/ZoomInfo FIND lists, then we qualify and score on firmographics + a buying signal. This file adds two layers that motion does not have:
1. **AI-native lead scoring** that derives the list from web + social-graph search (agent-powered) instead of buying it from a data vendor, with an explicit 0-100 weighted rubric.
2. **The network-growth / warm-path layer**: rank the mutuals who can introduce you, find the shortest warm chain to each target, pick the channel by warmth, and keep the underlying network healthy (prune / keep / grow) so warm paths actually exist.

This does NOT replace the 5-phase list build or the signal tiers; it sits beside them. Use the tool stack when the buyer is reachable cold and the vendor data is good; use this when the highest-value targets are operators/founders/investors whose real signal lives in public activity and whose best path in is a warm intro.

---

## Part A: AI-native lead intelligence (replaces the Apollo/Clay/ZoomInfo dependency)

### The pipeline
```
1. Signal scoring  ->  2. Mutual ranking  ->  3. Warm-path discovery  ->  4. Enrichment  ->  5. Outreach draft
```
Stage 1 + 4 + 5 are the lead-intelligence analogue of the base list build; stages 2 + 3 are the new network layer (Part B). Run voice capture (brand-voice) BEFORE any draft; never draft outbound from generic sales copy.

### Stage 1: Signal scoring (0-100, weighted rubric)
Replace "buy a list, then score firmographics" with "search public surfaces, score the person." For each candidate, score 0-100:

| Signal | Weight | How to assess |
|---|---|---|
| Role / title alignment | 30 | Decision-maker in the target space? |
| Industry match | 25 | Company/work directly in the target vertical? |
| Recent activity on topic | 20 | Posted / published / spoke on it recently? |
| Influence | 10 | Follower count, publication reach, speaking |
| Location proximity | 10 | Same city / timezone as you? |
| Engagement overlap | 5 | Interacted with your content or network? |

Search approach: deep web search (Exa-class) by vertical x role for company/person discovery, plus social search (X-class) for active voices on the topic, then dedupe and merge profiles into one record per person. Return top N sorted by score with a per-signal breakdown (e.g. `role=28/30, industry=24/25, activity=20/20, influence=8/10, location=10/10, engagement=4/5`).

**Hard rule: do not fabricate profile data.** Report only what search verifies; flag low-confidence scores where data is sparse; merge duplicates. This is the same evidence discipline as the base Phase-3 qualify step (source URLs + High/Med/Low confidence) applied to the AI-sourced record.

**How this maps to the base scoring.** The 0-100 score is the input to Hot/Warm/Cold/Skip, it does not override it: a high signal-score still needs a buying signal to earn Hot (base rule "Hot label without a buying signal is forbidden" stands). Role+industry+activity here ARE the falsifiable-ICP fit + the timing signal expressed numerically.

### Stage 4: Enrichment (per qualified lead)
Pull, from deep-search + social + GitHub (dev-centric) + the person's own site:
- Person: name, current title, company, handle/profile URLs, recent posts (last 30 days: topics, tone, key takes), talks/podcasts, OSS contributions, shared interests with the user.
- Company: size, stage, last funding (amount/date/investor), recent news (launch, pivot, hiring), tech stack, market position.
- Activity signals: last post date+topic, recent publications, conference attendance, job changes in last 6 months, company milestones.
Output a structured profile ending in **personalization hooks** (the 1-3 specific, recent things outreach will reference). Note "not found" rather than guessing; flag data older than 6 months as stale (same decay discipline as the base "re-verify before Hot").

### Stage 5: Outreach draft (voice-matched, channel-specific)
Draft must match the source-derived voice profile (run brand-voice first) AND the channel. Length caps:
- **Warm intro request (to the mutual): <= 60 words.** Greeting -> one-sentence ask -> one sentence why it is relevant -> offer a forwardable blurb -> sign off. Avoid overexplaining your company, social-proof stacking, or sounding like a fundraiser template.
- **Cold email (to target): <= 80 words.** Subject specific + under 8 words; opener references something specific/recent about them; 2-sentence pitch on why THEY care; one low-friction ask; sign off with one credibility anchor.
- **X / social DM: <= 40 words.** Reference a specific post/take; one line on why; clear ask.
- **Follow-up sequence:** day 4-5 short follow-up with one new data point; day 10-12 clean close; <= 3 touches total unless told otherwise. (Tighter than the base 5-email sequence on purpose: warm/social outbound is a different rhythm; the base cadence still governs vendor-sourced cold-email campaigns.)

**Draft anti-slop banned list (additive to the base banned phrases):** never use "game-changer", "deep dive", "the key insight", "leverage", "synergy", "at the forefront of". Plus the existing bans ("hope this finds you well", "just checking in", etc.). Lowercase-casual register; short sentences; data over adjectives; one ask per message; no fake familiarity ("loved your talk" only if you can cite the talk). If enrichment is thin, label the draft "needs manual personalization" rather than faking specifics.

**Drafts only, never auto-send.** Create the draft (Apple Mail / app draft when desktop control exists) and stop; sending requires explicit user approval. This generalizes the base "calendar link in message 2, not 1" friction discipline to the whole channel set.

---

## Part B: Network growth + warm-path layer (the new dimension)

Outbound is not a one-way prospecting list. The warmest path to a high-value target usually runs through someone you already know, and that only works if your network is curated toward your current priorities. Two motions: **map warm paths to targets**, and **grow/prune the network so paths exist**.

### Stage 2: Mutual ranking (who can introduce you)
For each scored target, inspect the user's social graph (X following, LinkedIn connections) and find shared connections. Rank each mutual as a bridge:

| Factor | Weight |
|---|---|
| Number of connections to your targets | 40 |
| Mutual's role / influence (decision-maker vs IC, investor, connector) | 20 |
| Location match (same city = easier intro) | 15 |
| Industry alignment (same vertical = natural intro) | 15 |
| Identifiability (clear handle / profile / email) | 10 |

Bridge math (use when you want the graph value itself):
```
B(m) = sum over targets t of  w(t) * lambda^(d(m,t) - 1)      # weighted, distance-decayed bridge value
R(m) = B_ext(m) * (1 + beta * engagement(m))                  # boosted by real engagement
```
Tiers from R(m): **Tier 1** high R + direct bridge -> ask for a warm intro; **Tier 2** medium R + one-hop bridge -> conditional intro ask; **Tier 3** no viable bridge -> direct cold outreach using the same lead record. Output a per-target warm-path report plus a mutual leaderboard ("@mutual_a connected to 7 targets, score 92").

**Hard rule: only report connections you can verify** from API/public-profile data. Do not infer a connection from similar bios or shared location alone; flag uncertain ones with a confidence level.

### Stage 3: Warm-path discovery (the shortest chain), ordered by warmth
1. **Direct mutual** (warmest) - you both follow/know the same person.
2. **Portfolio / advisory** - mutual invested in or advises the target's company.
3. **Co-worker / alumni** - shared employer or school.
4. **Event overlap** - same conference / accelerator / program.
5. **Content engagement** (coolest) - target engaged with the mutual's content recently.
For each target, surface the 1-2 shortest chains and the suggested approach ("ask Jane for the intro"; "reference Bob's Series A investment").

### Channel selection heuristic (pick ONE primary, in order)
1. warm intro by email  ->  2. direct email  ->  3. LinkedIn DM  ->  4. X DM or reply.
Go multi-channel only with a strong reason and a cadence that will not feel spammy. Channel-by-warmth here refines the base channel-by-persona map: persona sets the medium, warmth sets which lever (intro vs cold) you pull first.

### Network growth / pruning (connections-optimizer)
Keep the graph biased toward current priorities so warm paths exist. **Review-first, never blind auto-prune; never auto-send DMs/invites/emails; emit a ranked plan + drafts before any apply step.**

Inputs to collect/infer: current priorities + active work, target roles/industries/geos, platform (X / LinkedIn / both), a do-not-touch list, and a mode.

Modes:
- **light-pass** - prune only high-confidence low-value one-way follows; surface the rest for review; small add list.
- **default** - balanced prune queue + keep list + ranked add/follow queue + draft warm intros where useful.
- **aggressive** - larger prune queue, lower tolerance for stale non-follow-backs, still review-gated.

Platform rules:
- **X:** prune only accounts you follow, never your followers; mutuals are stickier than one-way follows; non-follow-backs can be pruned harder; surface disappeared/inactive accounts fast; engagement + signal + bridge value beat raw follower count.
- **LinkedIn:** API-first if the user actually has access, else browser workflow; outbound follows can be pruned freely; accepted 1st-degree connections default to manual review, not auto-remove.

Scoring (which to keep vs cut):
- **Positive:** reciprocity, recent activity, alignment to current priorities, network bridge value, role relevance, real engagement history, recent presence/responsiveness.
- **Negative:** disappeared/abandoned account, stale one-way follow, off-priority topic cluster, low-value noise, repeated non-response, no follow-back when many better replacements exist.
- Mutuals and real warm-path bridges are penalized less aggressively than one-way follows.

Review-pack format: Mode / Platforms / Priority Set; then **Prune Queue** (handle, reason, confidence, action) - **Review Queue** (handle, reason, risk) - **Keep / Protect** (handle, bridge value) - **Add / Follow Targets** (person, why now, warm path, preferred channel) - **Drafts** (X DM / LinkedIn / Apple Mail). Run brand-voice before drafting.

---

## When -> Do (additions to the base decision rules)
- **When** the top targets are operators/founders/investors whose real signal is public activity, or vendor data is thin -> run AI-native signal scoring (0-100 rubric) instead of buying a list; feed the score into Hot/Warm/Cold/Skip (signal score never overrides the buying-signal requirement for Hot).
- **When** a target is high value -> map mutuals (bridge ranking) and find the shortest warm chain BEFORE writing a cold email; if Tier 1/2 bridge exists, draft a warm-intro request to the mutual first.
- **When** picking a channel -> warm-intro email > direct email > LinkedIn DM > X DM; one primary channel, multi-channel only with a real reason.
- **When** drafting AI-sourced outreach -> brand-voice first, channel word-caps (60 intro / 80 email / 40 DM), anti-slop ban list, drafts only (never auto-send).
- **When** warm paths keep coming up empty, or the user asks to "clean up / grow my network", "who should I unfollow/follow/reconnect with" -> run connections-optimizer (review-first; X prune-follows-only; LinkedIn 1st-degree review-first).

## Boundaries (no duplication)
- The 5-phase tool-based list build, signal tiers (T1/T2/T3), sequence cadence, deliverability hard rules, and compliance lineage all stay as-is in rules.md / SKILL.md. This file adds the AI-native scoring rubric and the warm-path + network-growth layer only.
- Bridge math and standalone network scoring are the methodology of ECC's social-graph-ranker; we carry the model inline here and do not bundle its code.
- Verified warm threads still hand off to Sales Engineer with signal + path + objection context (base handoff rule).
