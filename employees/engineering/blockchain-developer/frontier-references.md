# Blockchain Developer - Frontier References

Methodology lifted from verified 2026 sources (see TOP5-CANDIDATES.md for stars/license/recency).
Concepts and architecture only. No copyleft or unlicensed code is bundled here; flagged sources
(GPL / AGPL / no-license) contribute reworded methodology plus a self-host note. Last revised 2026-06-13.

---

## 1. Account Abstraction depth (ERC-4337 + EIP-7702)
Source: eth-infinitism/account-abstraction (GPL-3.0, 1.9k stars, v0.9.0 2025-11-16, used-by 11.2k).
GPL → architecture/methodology only; host installs `@account-abstraction/contracts` for real builds, never vendor it in.

- **EntryPoint is the singleton hub.** v0.8 EntryPoint is canonically deployed at
  `0x4337084d9e255ff0702461cf8895ce9e3b5ff108` on most EVM chains; v0.9 is the latest release line.
  Never deploy your own EntryPoint - target the canonical one and pin its version per chain (the
  PackedUserOperation layout and validation rules changed across v0.6 → v0.7 → v0.8).
- **The four core roles to reason about:** EntryPoint (validates + executes UserOps, handles refunds),
  BaseAccount (your smart account, implements `_validateSignature`), BasePaymaster (sponsors gas via
  `_validatePaymasterUserOp`), StakeManager + NonceManager (deposit/stake + 2D nonces).
- **Validation return-data is packed**, not a bool: `_packValidationData(sigFailed, validUntil, validAfter)`.
  Returning the wrong packing silently bricks time-bounded sessions - test the boundaries.
- **Paymaster trust model:** a sponsoring paymaster runs attacker-supplied UserOps; treat
  `_validatePaymasterUserOp` as a hostile entrypoint, bound what you sponsor, and use `context`/`postOp`
  carefully (postOp can be called twice on revert in older versions).
- **EIP-7702 (Pectra) is now in scope.** An EOA can delegate to contract code; Simple7702Account shows the
  EOA-as-smart-account pattern (batching via 7702 + gas sponsoring via 4337). Decision rule: 7702 for
  upgrading an existing EOA in place; full 4337 account when you need counterfactual deploy + recovery.
- **Bundler/mempool is a separate trust domain:** the alt-mempool can drop or reorder UserOps; do not assume
  inclusion. For client integration use a hosted bundler (Pimlico/Alchemy) or eth-infinitism/bundler reference.

## 2. Slither detector triage map
Source: crytic/slither (AGPL-3.0, 5.9k stars, active 2026), Trail of Bits.
AGPL → SELF-HOST only: Slither is a standalone CLI run on the dev machine / in CI, never linked into
deliverable contract code, so its copyleft does not reach the client. This is already the prescribed usage;
what is new here is the finding taxonomy so "run Slither and triage" becomes actionable.

Run `slither . ` then `slither --list-detectors` for the full set (90+). Triage by impact:

- **High (block the PR):** `reentrancy-eth` (reentrancy with ETH at risk), `arbitrary-send-eth`
  (funds to a user-controlled address), `suicidal` (anyone can selfdestruct), `controlled-delegatecall`,
  `uninitialized-state`, `uninitialized-storage`, `unprotected-upgrade`, `weak-prng`.
- **Medium:** `reentrancy-no-eth`, `shadowing-state`, `incorrect-equality` (strict `==` on balances),
  `locked-ether` (payable contract with no withdraw), `tx-origin`, `unchecked-transfer`,
  `divide-before-multiply`, `erc20-interface` mismatches.
- **Low / Informational:** `reentrancy-benign`, `reentrancy-events`, `timestamp` dependence,
  `assembly` usage, `naming-convention`, `solc-version`, `low-level-calls`, `dead-code`.
- **Triage rule:** every High/Medium is either fixed or has a written justification (false-positive +
  why) committed alongside the code - never a silently ignored finding. Feed the suppressions list into
  the audit-readiness pack so auditors see your reasoning. Pair Slither (fast, broad) with the
  property-based fuzz/invariant ladder (deep, targeted) - neither replaces the other.

## 3. Audit-finding checklist categories (per-finding "what to look FOR")
Source: Cyfrin/audit-checklist - Solodit aggregated checklist (NO LICENSE → concepts-only, attributed;
358 stars, living doc). Aggregates 12 named auditor checklists (Beirao, Decurity, Hans, Jeffrey, Jonas,
Miguel, Nisedo, Owen, Rahul, Rajeev, RareSkills, Roman). Distilled below; the canonical structured form
(ID / question / description / remediation / references per item) lives at solodit.cyfrin.io/checklist.

This is the active-search layer below the nascent audit-readiness gate (which asks "is the repo ready?").
These ask "what specific bug class might be hiding here?":

- **Accounting & math:** rounding direction always favors the protocol; precision loss documented;
  share-price manipulation via direct token donation; first-depositor inflation; mixing virtual and
  real balances; fee-on-transfer received < sent.
- **Access control:** every privileged function gated and event-logged; two-step ownership transfer;
  role can't be renounced into a brick; initializer front-running on proxies.
- **External calls & reentrancy:** CEI on every state-changing path; read-only reentrancy (view returns
  stale mid-callback); cross-function and cross-contract reentrancy, not just same-function.
- **Oracles:** staleness check (`updatedAt`), sequencer-uptime feed on L2 (Arbitrum/Optimism), min/max
  answer bounds, no spot-price-as-oracle, decimals mismatch between feeds.
- **Tokens held:** the weird-token matrix already in rules.md, plus approval race and non-standard
  return values.
- **Upgradeability:** storage-slot collision on upgrade; gap arrays; `_disableInitializers()` in
  the implementation constructor; unprotected `upgradeTo`.
- **DoS:** unbounded loops over user-growable arrays; griefing a batch via one reverting recipient
  (pull-over-push); gas-limit reachable.
- **Signatures:** EIP-712 domain includes chainid + verifyingContract; nonce per signer; signature
  malleability (low-s); replay across forks/upgrades; deadline present.

## 4. Gas-optimized building blocks (Solady)
Source: Vectorized/solady (MIT, 3.3k stars, v0.1.26 2025-08-25). MIT → could be vendored, but carried as
methodology + CONNECT (`forge install vectorized/solady`); the employee recommends libraries, not copies.

- **Reach for a battle-tested optimized lib before hand-rolling assembly.** Solady is the upstream lab
  for Solmate and is heavily audited. When gas on a hot path actually matters and OZ is too heavy,
  Solady is the default - auditors know it.
- **High-value modules:** `SafeTransferLib` (handles missing-return ERC20 + ETH, cheaper than OZ
  SafeERC20), `ReentrancyGuard` (transient-storage based), `LibClone` + `ERC1967Factory` (minimal-proxy
  and deterministic CREATE3 deploys), `EIP712`, `ECDSA` / `SignatureCheckerLib` (EOA + ERC-1271),
  `FixedPointMathLib`, `MerkleProofLib`, `LibString` / `Base64` (on-chain metadata).
- **AA + passkeys:** Solady ships ERC4337 + ERC4337Factory, ERC7821 (batch executor mixin), LibERC7579,
  ERC6551 (token-bound accounts), `P256` + `WebAuthn` (passkey signature verification), and
  `LibEIP7702` / EIP7702Proxy - useful primitives alongside the eth-infinitism architecture above.
- **Caveat (document it):** some Solady modules use partial-EVM-incompatible opcodes; on ZKsync-stack
  chains run `prep/zksync-compat-analysis.js` and use the `ext/zksync` substitutes or fall back to OZ.

## 5. wagmi v3 frontend workflow (retires the old list-level note)
Source: wevm/wagmi (MIT, 6.7k stars, wagmi@3.6.16 2026-05-26). Tier-1 source now mined - Workflow 6's
"HONEST DEPTH NOTE: list-level" is retired.

- **v3 is the current major** (v2 hooks names mostly carry over; check the v2→v3 migration guide for
  config + connector deltas before copying older snippets).
- **Setup:** `createConfig({ chains, transports, connectors })` → wrap app in `WagmiProvider` +
  TanStack `QueryClientProvider` (wagmi v2/v3 require the query client) → RainbowKit `ConnectButton`
  for wallet UI. Connectors: `injected()`, `walletConnect({ projectId })`, `coinbaseWallet()`;
  EIP-6963 multi-wallet discovery is built in.
- **Reads:** `useReadContract` (single), `useReadContracts` (multicall batch), `useBalance`,
  `useBlockNumber({ watch: true })` for live updates.
- **Writes (the correct sequence):** `useSimulateContract` first to surface the revert reason BEFORE the
  wallet popup → pass its `data.request` into `useWriteContract().writeContract` →
  `useWaitForTransactionReceipt({ hash })` to track mined/confirmed. Never sign blind.
- **UX rules (enforce):** handle wrong-network with `useSwitchChain`; render pending / confirming /
  success / reverted as distinct states; surface the decoded revert reason from simulation; never leave
  a spinner on a dropped or replaced tx (watch for replacement in the receipt hook).
- **Gasless / AA:** wire the ERC-4337 stack from reference 1 (Pimlico/Alchemy bundler + paymaster) behind
  the same write hooks when the client wants no-gas onboarding.

---

## Small-task / prototype lane (operational, not absorbed)
Not every request is a mainnet protocol. Right-size the process to the stakes:

- **PROTOTYPE / throwaway / testnet-only, no real value:** OZ contracts + a Foundry happy-path test +
  one Slither pass. Skip the full 8-rung ladder, skip the audit pack. STILL banned even in prototypes:
  `tx.origin` auth, `transfer()`/`send()` for ETH, unbounded loops, spot-price oracles - bad habits
  calcify. Label the deliverable "PROTOTYPE - not audited, do not hold real value."
- **SMALL TASK on an existing audited codebase** (add a view, tweak a constant, wire an event): match the
  surrounding conventions (MetaGPT SOP), add the concrete + revert tests for the touched path, run
  Slither on the diff, no version bump to the audit scope unless storage or an external call changed.
- **REAL TVL / mainnet / anything custodial:** the full pipeline in rules.md is mandatory, no lane.
- **Escalation trigger:** the moment a "prototype" is going to hold real funds or mainnet-deploy, it
  re-enters the full secure-development pipeline from the Spec step - there is no graduating a toy.
