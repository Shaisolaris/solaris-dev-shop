# WordPress Master - TOP 5 verified 2026 candidates

Domain: WordPress build / diagnostics. Verified 2026-06-13.

| # | Source | Stars/Status | License | Last update | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|--------------|---------|-------------|------------|--------------|--------|-----|
| 1 | https://github.com/WordPress/mcp-adapter | v0.5.0 plugin | GPL-2.0+ (FLAG copyleft; methodology only) | 2026 | WordPress (AI Team) | The MCP Adapter is a SEPARATE plugin (v0.5.0), NOT in core, on its own cadence. Corrects the file's conflation of "Abilities API + MCP Adapter" as one install. | grep: "MCP Adapter" present but treated as one install w/ Abilities API = accuracy fix | METHODOLOGY (correct the install model) |
| 2 | WordPress Abilities API (core since Nov 2025) | core (WP 6.9/7.0) | GPL (core) | 2026 | WordPress | Now CORE - no install needed; register abilities, MCP Adapter exposes them. File treats it as installable. | grep: present but mis-stated as install = accuracy fix | METHODOLOGY (core-status fix) |
| 3 | WordPress 7.0 AI Client / PHP AI Client (ships 2026-05-20) | core 7.0 | GPL | 2026 | WordPress | NET-NEW core AI surface in WP 7.0 - a standard client for AI calls from PHP; the surface plugin devs should learn alongside Abilities/MCP. Absent from the file. | grep: "AI Client"/"7.0" ABSENT = not a content-duplicate | ABSORB methodology / CONNECT |
| 4 | https://github.com/WordPress/agent-skills | 13 skills, official | GPL-2.0+ (methodology absorbed in own voice) | 2026 | WordPress | Already the modern-stack source. Confirmed official + active (13 skills). | grep: present = content-duplicate | ABSORB (confirmed) |
| 5 | WordPress 6.9 (Dec 2025) perf + Interactivity API iteration | core | GPL | 2025-12 | WordPress | 2.8-5.8% (up to 10-15%) perf uplift: template output buffer, minified+inlined CSS, smarter caching; Interactivity API better fetch priority + client-side nav. | grep: 6.9 perf specifics ABSENT = refresh | METHODOLOGY (perf refresh) |

## Notes
- Key accuracy fixes (not new sources): (a) Abilities API is now CORE (since Nov 2025, WP 6.9/7.0) - no install; (b) MCP Adapter is a SEPARATE plugin v0.5.0 on its own cadence - the file conflated them as one install.
- Net-new: WP 7.0 (May 20 2026) ships the AI Client / PHP AI Client - a core AI surface the file is missing.
- Refresh: WP 6.9 perf uplift specifics + Interactivity API iteration.
- All GPL - methodology absorbed in Solaris voice (the existing license-safe pattern); no code copied.
