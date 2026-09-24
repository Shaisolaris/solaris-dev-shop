# Blockchain Developer - Top-5 Verified 2026 Source Candidates

Compiled 2026-06-13. All stars / licenses / commit-recency verified live against github.com the same day (HTML repo pages + Slither/Cyfrin via cross-search). Gate-0 = grep of this employee's ACTUAL content (SKILL.md + rules.md + plugin.json + learnings.md), not the description blurb.

Existing absorbed canon (do not re-absorb): wshobson blockchain-web3 (4 skills), nascentxyz simple-security-toolkit (4 docs), solcurity concepts, VoltAgent cross-check, msitarzewski legacy, MetaGPT SOP, foundry-mcp + evm-mcp (CONNECT).

---

## 1. eth-infinitism/account-abstraction  - ABSORB (METHODOLOGY) + FLAG
- **URL:** https://github.com/eth-infinitism/account-abstraction
- **Stars:** 1.9k  ·  **Used-by:** 11.2k dependents (canonical ERC-4337 reference impl)
- **License:** GPL-3.0  ←  **FLAGGED (copyleft)** - methodology + self-host note only, no code bundled
- **Last release / commit:** v0.9.0 published 2025-11-16; `develop` active (438 commits)
- **Maintainer:** eth-infinitism (Yoav Weiss et al; the ERC-4337 authors / EntryPoint deployers)
- **What it adds:** the real Account Abstraction model the employee currently only name-drops. EntryPoint v0.8 canonical singleton address (0x4337084d9e255ff0702461cf8895ce9e3b5ff108), PackedUserOperation struct, BaseAccount / BasePaymaster / StakeManager / NonceManager roles, `_validateSignature` / `_validatePaymasterUserOp` return-data packing (validUntil/validAfter), and **Simple7702Account** (EIP-7702 + 4337 combo - net-new topic entirely).
- **Gate-0:** all 4 "EntryPoint" grep hits are the FREI-PI "function entrypoint" phrase, NOT the 4337 EntryPoint contract. `7702`, `PackedUserOperation`, `BasePaymaster`, `StakeManager` = 0 hits. Current AA coverage is one clause ("ERC-4337 (Pimlico/Alchemy bundlers, paymaster sponsorship)"). → **net-new, not content-duplicate.**
- **Tag:** METHODOLOGY (AA architecture + EIP-7702) - GPL so concepts/architecture only, host installs the package for real builds.

## 2. Vectorized/solady - CONNECT + METHODOLOGY
- **URL:** https://github.com/Vectorized/solady
- **Stars:** 3.3k  ·  1,641 commits
- **License:** MIT  ←  permissive, preferred
- **Last release:** v0.1.26 (2025-08-25); main branch active
- **Maintainer:** Vectorized (z0r0z et al); upstream lab for Solmate
- **What it adds:** gas-optimized building-block library the employee's gas section gestures at but never names. SafeTransferLib (missing-return ERC20/ETH), ERC4337 + ERC7821 (batch executor) + ERC7579 account mixins, LibClone + ERC1967Factory (minimal-proxy / deterministic deploys), ReentrancyGuard, EIP712, P256 + WebAuthn (passkey accounts), ERC4626 with built-in inflation defense. ZKsync partial-EVM compat caveats documented.
- **Gate-0:** `solady`, `SafeTransferLib` = 0 hits anywhere. The "Solmate only where gas is paramount" rule exists but Solady (its successor lab) is absent. → net-new.
- **Tag:** CONNECT (host-installed lib via `forge install vectorized/solady`) + METHODOLOGY (its gas/proxy/account patterns inform rules.md). MIT so could be bundled, but employees carry methodology not vendored code → methodology + connect note.

## 3. Cyfrin/audit-checklist (Solodit aggregated checklist) - METHODOLOGY + FLAG
- **URL:** https://github.com/Cyfrin/audit-checklist  ·  hosted: https://solodit.cyfrin.io/checklist
- **Stars:** 358 (notable maintainer: Cyfrin / Solodit, the dominant Web3-audit aggregator)
- **License:** **NONE shown → NOASSERTION - FLAGGED** (same posture as solcurity: concepts-only, attributed)
- **Last commit:** actively maintained (Cyfrin 2025 wrap-up cites "fully updated checklist page"); 34 commits, living document
- **Maintainer:** Cyfrin (Patrick Collins et al)
- **What it adds:** a structured, queryable audit-finding checklist (each item = ID + question + description + remediation + references) aggregating 12 named auditor checklists (Beirao, Decurity, Hans, Jeffrey, Jonas, Miguel, Nisedo, Owen, Rahul, Rajeev, RareSkills, Roman). Goes one layer deeper than the nascent audit-readiness gate already absorbed: per-category finding prompts (the "what to look FOR", not just "is the repo ready").
- **Gate-0:** `solodit` and `Cyfrin` appear ONLY in build_notes ("evaluated, not absorbed - no license, redundant") and learnings.md ("NEXT-BUMP CANDIDATE"). Zero checklist *content* present. `remediation` = 0 hits. → net-new; prior rejection was a deferral, now actioned as concepts-only.
- **Tag:** METHODOLOGY (concepts-only, attributed, no-license) - distil category prompts into the audit reference, do not copy checklist.json verbatim.

## 4. crytic/slither - METHODOLOGY + SELF-HOST + FLAG
- **URL:** https://github.com/crytic/slither
- **Stars:** 5.9k  ·  actively maintained (commits through 2026)
- **License:** **AGPL-3.0 - FLAGGED (strong copyleft)** - methodology + self-host note only
- **Last commit:** 2026 (master active); slither-action v0.4.2 Jan 2026
- **Maintainer:** Trail of Bits (crytic)
- **What it adds:** the employee mandates "Slither in CI / triage everything" but never enumerates WHAT Slither finds. Lift the detector taxonomy as a triage map: reentrancy family (reentrancy-eth / -no-eth / -benign / -events / -unlimited-gas), arbitrary-send-eth, uninitialized-state / -storage, shadowing-state, suicidal, locked-ether, tx-origin, unchecked-transfer, incorrect-equality, etc., grouped by High/Medium/Low/Informational impact + `--list-detectors` workflow. Turns "run Slither" into "here is the finding map and how to triage each class".
- **Gate-0:** `Slither` named 6x (run-it / triage-it / CI), but `detector`, `reentrancy-eth` = 0 hits. The taxonomy itself is absent. → net-new methodology layer on an already-referenced tool.
- **Tag:** METHODOLOGY (detector taxonomy + triage) + SELF-HOST (AGPL: it is a standalone CLI run on the user's machine, never linked into deliverable code - already the existing usage, so AGPL is non-contaminating).

## 5. wevm/wagmi - METHODOLOGY / CONNECT (closes self-flagged gap)
- **URL:** https://github.com/wevm/wagmi
- **Stars:** 6.7k  ·  1.4k forks
- **License:** MIT  ←  permissive, preferred
- **Last release:** wagmi@3.6.16 (2026-05-26) - **wagmi v3 is now current**
- **Maintainer:** wevm (also maintains viem)
- **What it adds:** directly retires Workflow 6's "HONEST DEPTH NOTE: list-level, no Tier-1 wagmi source mined." v3 hooks surface + correct patterns: useReadContract / useWriteContract / useSimulateContract / useWaitForTransactionReceipt, connector config (injected / WalletConnect / Coinbase), chain-switch + wrong-network handling, query-client integration, and the v2→v3 migration deltas the current list-level text predates.
- **Gate-0:** `useReadContract` / `useWriteContract` / `useSimulateContract` each appear exactly once (SKILL.md L59) at list level; `wagmi v3` = 0 hits; the workflow self-declares list-level. → net-new DEPTH on a named-but-shallow area.
- **Tag:** METHODOLOGY (v3 hooks workflow into the frontend section) + CONNECT (it is the runtime dep the dapp installs).

---

## Selection rationale vs alternatives considered
- **scaffold-eth/scaffold-eth-2** (MIT, ~1.8k, the originally-queued candidate): a boilerplate template, not a methodology source; its wagmi value is better taken from wagmi upstream (#5). Demoted.
- **OpenZeppelin/openzeppelin-contracts**: already the deep canonical backbone throughout rules.md - content-duplicate, skipped.
- **pcaversaccio/snekmate** (AGPL, Vyper): off-stack (Vyper, not Solidity/EVM-Solidity focus) - skipped.
- **pimlicolabs/permissionless.js**: useful for AA bundler client, but eth-infinitism (#1) is the canonical primitive; revisit as a future CONNECT.

## Flag summary for Shai
- GPL-3.0: eth-infinitism/account-abstraction (#1)
- AGPL-3.0: crytic/slither (#4)
- NOASSERTION / no license: Cyfrin/audit-checklist (#3)
- All three handled as METHODOLOGY / concepts-only + self-host; no copyleft or unlicensed code bundled into the employee or into deliverables.
