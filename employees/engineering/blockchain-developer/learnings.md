# Blockchain Developer - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from msitarzewski solidity-engineer**: Security-first principles (no tx.origin, no transfer, CEI pattern) + Foundry >95% coverage + external audit before mainnet are the consistent professional standards.
- **2026-04-25 - Custom errors over require strings** is the gas optimization with biggest impact + clarity benefit.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| 2026-06-13 | AA/EIP-7702 + Slither triage + audit-finding categories + Solady + wagmi v3 | frontier-references.md |

## 2026-05-01 - M4 absorption: MetaGPT Engineer spec→code handoff (v0.4.0)
- Pattern: 8-step sequence; schema discipline (verbatim signatures); no scope creep; imports from Shared Knowledge
- Anti-patterns refused: improvements, helper additions, renames
- Source: github.com/FoundationAgents/MetaGPT

## 2026-06-09 - v0.5.0 rebuild from real sources
- nascentxyz simple-security-toolkit's 22-step process + FREI-PI is the spine of the dev workflow now; its "// Safety:" unchecked-comment convention adopted as a hard rule.
- solcurity could only be absorbed as concepts (no LICENSE file) - distilled ~20 checks into rules.md red flags/decision rules with attribution.
- NEXT-BUMP CANDIDATES (updated 2026-06-13): wagmi/viem list-level gap CLOSED via wagmi v3 upstream (v0.7.0); Cyfrin/Solodit checklist ACTIONED as concepts-only (v0.7.0). Still open: wshobson skills' references/details.md for nft-standards + defi-protocol-templates + web3-testing not yet mined (only solidity-security's was); pimlicolabs/permissionless.js as a future AA-bundler CONNECT; eth-infinitism/bundler if running an own bundler.

## 2026-06-13 - v0.7.0 deepen pass (frontier-references.md)
- Lifted 5 verified 2026 sources as METHODOLOGY into new frontier-references.md, registered in plugin.json references.
- eth-infinitism/account-abstraction (GPL, concepts + self-host): EntryPoint v0.8 canonical addr, PackedUserOperation, BaseAccount/BasePaymaster/StakeManager/NonceManager, validation-data packing, Simple7702Account (EIP-7702 x 4337). Gate-0 net-new (prior 'EntryPoint' hits were FREI-PI 'function entrypoint').
- crytic/slither (AGPL, self-host CLI): detector triage map by impact + suppression-justification rule.
- Cyfrin/audit-checklist Solodit (no license, concepts, attributed): per-category audit-finding prompts; reverses the v0.5.0 'evaluated not absorbed' deferral as concepts-only.
- Vectorized/solady (MIT): gas building blocks (SafeTransferLib, LibClone, ReentrancyGuard, ERC4337/7821/7579, P256/WebAuthn) + ZKsync caveat. CONNECT + METHODOLOGY.
- wevm/wagmi (MIT): v3 hooks workflow (simulate then write then waitForReceipt). Retired Workflow 6 list-level note.
- Part B same pass: removed phantom phase_artifacts (sources/_analysis/ dir absent), added small-task/prototype lane, fixed stale wagmi/AA reference rows, tightened cross-refs. TOP5-CANDIDATES.md written.
- FLAGS for the owner: GPL (eth-infinitism), AGPL (slither), no-license (Cyfrin), all handled methodology/self-host only, no code bundled.
## Sources

- Upstream: eth (license not recorded); Vectorized/solady (license not recorded); Cyfrin/audit (license not recorded); crytic/slither (license not recorded); wevm/wagmi (license not recorded)
- What was used: methodology absorbed: eth; methodology only: Vectorized/solady, Cyfrin/audit, crytic/slither, wevm/wagmi; connected as external reference: Vectorized/solady, wevm/wagmi
- License notes: licenses not recorded in scan for: eth, Vectorized/solady, Cyfrin/audit, crytic/slither, wevm/wagmi - verify before reuse; no code vendored
