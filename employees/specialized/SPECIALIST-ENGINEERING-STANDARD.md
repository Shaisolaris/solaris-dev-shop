# Specialist Engineering Operating Standard (2026-07)

Status: active for blockchain, AR/VR, IoT, Unity, Unreal, and WordPress capabilities
Wave: skill-je0 / skill-wave-specialist-engineering-20260724
Synthetic and professional only. No production keys, devices, or store submissions in fixtures.

This standard upgrades platform compatibility, security, build/test, licensing, and
artifact evidence without inventing engine results or bypassing human authority for
deployments, chain transactions, device mutation, or store hosting changes.

## 1. Platform and engine contracts (HARD)

Every deliverable that claims engine/SDK work must name:
- **target_platform**: chain/network, XR runtime, MCU/board, Unity/Unreal version, or WP/PHP version
- **sdk_or_tool_pin**: version or commit of compiler, engine, Foundry, WP-CLI, etc.
- **availability**: present | missing | unlicensed | unknown

If availability is missing/unlicensed/unknown for a required tool:
- status is `PARTIAL` or `BLOCKED`
- list the missing item and a supported alternative (simulator, fixture, CI plan, docs-only)
- never invent test results, screenshots, cook logs, or on-chain receipts

## 2. Security practices (HARD)

| Domain | Baseline |
|--------|----------|
| Blockchain | CEI, reentrancy/oracle/signature defenses, no keys in repo, testnet-first |
| AR/VR | permission purpose disclosure, no silent sensor access, comfort/safety notes |
| IoT | no hardcoded device credentials, secure boot/OTA notes when relevant, least privilege |
| Unity/Unreal | no untrusted package execution, sandbox editor automation, secret hygiene |
| WordPress | capability lockdown, supply-chain review, no prod credentials in git, staging first |

Prohibited patterns:
- private keys, mnemonics, production DB passwords in repo artifacts
- mainnet value-moving transactions without human authority
- physical device flash/OTA to production without approval
- store submission or production hosting mutation without approval
- executing untrusted plugins, Asset Store packages, or marketplace binaries without review

## 3. Licensing and assets (HARD)

Before recommending or executing third-party code/assets:
1. Record SPDX or license name (or `UNKNOWN`).
2. Record commercial/EULA constraints that affect redistribution or shipping.
3. If license is unknown or forbids the intended use => `BLOCKED` for ship path.
4. Prefer official/open sources with pinned provenance over anonymous blobs.

Licensed engine installs (Unity, Unreal) are human-owned; skills never install engines silently.

## 4. Build, test, and artifact evidence (HARD)

Successful technical paths include:
- build or test command planned or run
- artifact paths (logs, reports, coverage, screenshots, bytecode verification notes)
- explicit fail notes when tools unavailable

Refuse the literal line `Gate: passed` without evidence or an explicit human waiver.

## 5. Compatibility and fail-closed unavailability

Compatibility claims must cite the pinned platform matrix (engine version, PHP, EVM, board).
When hardware, licenses, SDKs, MCP bridges, or RPC endpoints are unavailable:
- fail closed (`PARTIAL`/`BLOCKED`)
- offer a synthetic or docs-only alternative
- do not claim PIE/cook/fork/device success

## 6. Approval, receipts, failure, rollback

External mutations stop at approval_preview (see department RUNTIME-POLICY where present).

Approval preview shape (mandatory):
```text
APPROVAL_PREVIEW
action: <deploy|mutate_external|network|store_submit|device_flash|...>
target: <system/platform>
payload_summary: <what would happen>
risk: <low|med|high> + why
authority_needed: <role/name level>
sources_for_claims: <list or UNVERIFIED>
status: AWAITING_HUMAN_AUTHORITY
```

Receipt shape when authorized:
```text
RECEIPT
action: <...>
authority_ref: <human id / ticket>
payload_summary: <what ran>
result: <success|partial|failed>
artifacts: <paths>
rollback_hint: <how to undo>
```

Failure: preserve drafts and partial artifacts; no retry loops that spend gas, flash devices, or publish.
Rollback: prior capability version remains the rollback_target; no history rewrites.

## 7. Provenance ledger

Every absorbed external method records: URL | title | date | license | what was taken.
Pins live in the wave `provenance.json` and may be mirrored in skill frontier/learnings notes.

## 8. Prohibited (wave scope)

- Chain transactions, device mutation, licensed engine installation, store submission,
  hosting production changes, or production deployment from evaluation fixtures
- Executing untrusted plugins or assets
- Secrets/credential changes or Gas Town control-plane changes

## 9. Gate line

End successful deliverables with the literal line: `Gate: passed`
only when platform, security, license, and evidence checks that apply are satisfied
or explicitly waived by human authority.
