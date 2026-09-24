# Healthcare Software-Development Compliance (dev-shop delivery layer)

Absorbed 2026-06-14 (methodology only, no code bundled) from ECC (affaan-m/ECC, formerly affaan-m/everything-claude-code, MIT) skills: healthcare-emr-patterns, healthcare-cdss-patterns, healthcare-phi-compliance, hipaa-compliance, healthcare-eval-harness (patient-safety CI gate), and the healthcare-reviewer agent. Original clinical methodology contributed by Dr. Keyur Patel, Health1 Super Speciality Hospitals.

**Why this lane exists:** Solaris is a dev shop that may BUILD healthcare software for clients. The existing GRC catalog (SOC 2 / ISO 27001 / EU AI Act / GDPR / PCI) tells us how to pass a paper audit. This layer is the engineering-delivery overlay: how to actually ship HIPAA-compliant, EMR/EHR-integrated, PHI-safe software and survive a healthcare audit on the built artifact, not just the policy binder. It does NOT duplicate the generic GRC machinery in rules.md - it sits on top of it.

**Gate-0 (what is already covered, NOT re-lifted):** generic framework gap matrices, evidence-as-scheduled-ticket, DPIA/DPA, breach clock + log + investigator, common-controls cross-map, compliance-as-code/OSCAL, vendor VTR loop, white-label readiness report shape. HIPAA was already a named framework in the catalog. What is NET-NEW here: HIPAA Privacy/Security/Breach rule decomposition AS IT LANDS IN SOFTWARE, PHI handling patterns in code, EMR/EHR clinical-safety patterns, CDSS safety, HL7/FHIR interop compliance, and the patient-safety deployment gate.

---

## 1. HIPAA decomposed for builders (Privacy / Security / Breach rules in software terms)

HIPAA is not one thing. Scope it as three rules plus the BAA chain, and translate each to a buildable control. Legal interpretation of the statute routes to legal-advisor; we scope, build, and evidence.

### Decision gates (run first on any healthcare engagement - hipaa-compliance overlay)
1. Is the data **PHI**? (identifies a patient AND relates to health/payment/care - see classification below.)
2. Is the actor a **covered entity** (provider/plan/clearinghouse) or a **business associate** (vendor handling PHI on a CE's behalf)? A dev shop building/hosting/processing PHI for a client IS a business associate.
3. Does any **vendor or model provider need a BAA** before touching the data? Treat every third-party SaaS, observability tool, support tool, and LLM provider as **blocked-by-default until BAA status + data boundary are confirmed.**
4. Is access limited to the **minimum necessary** scope?
5. Are read / write / export events **auditable**?

### Privacy Rule -> software
- **Minimum necessary** becomes scoped authorization: the right user sees the smallest PHI slice needed. Build it as role-scoped queries, not all-rows-then-filter-in-UI.
- **Right of access / amendment** becomes patient-facing export + the locked-record-plus-addendum pattern (see EMR section) so amendments never overwrite the original.
- **Accounting of disclosures** becomes the audit trail (every read/print/export logged).

### Security Rule -> software (the three safeguard families, as controls)
- **Administrative:** access provisioning/deprovisioning (maps to the existing CC6 offboarding ticket pattern), workforce training, sanction policy, contingency plan. Reuse the generic evidence-ticket machinery.
- **Physical:** facility access, workstation use, device/media controls (maps to existing datacenter/workstation/media-disposal policies).
- **Technical:** access control (unique user IDs, auto-logoff/session timeout), audit controls (the insert-only tamper-proof log), integrity (no silent modification), transmission security (encryption in transit), encryption at rest. These are the ones a build engagement must actually implement and the eval harness must verify.

### Breach Notification Rule -> posture
- Reuse the existing breach clock (discovered = known-or-should-have-been-known), named investigator, breach log, >=7y retention. HIPAA-specific overlays: 60-day individual notification, HHS notification (within 60 days if >=500 individuals, else annual log), and media notice for >=500 in a state/jurisdiction. The Security Rule risk-assessment determines whether an incident is a reportable breach.

### BAA chain (the dev-shop's own exposure)
- A signed **BAA between Solaris and the client (covered entity)** is a precondition to touching PHI - it is the contractual analogue of the DPA. Legal terms route to legal-advisor; the auditor confirms it exists and is scoped before any PHI flows.
- **Flow-down:** every subprocessor in the build (cloud host, error tracker, analytics, email, LLM) needs its own BAA or must be kept off the PHI path. This mirrors the GDPR subprocessor flow-down already in rules.md - same loop, BAA instead of DPA.

---

## 2. PHI/PII handling in code (healthcare-phi-compliance)

Three layers: **classification** (what is sensitive), **access control** (who can see it), **audit** (who did see it).

### Classification
- **PHI** = anything that can identify a patient AND relates to their health/care/payment: name, DOB, address, phone, email, national IDs (SSN/Aadhaar/NHS number), MRN, diagnoses, meds, labs, imaging, insurance/claim detail, appointment/admission records, or any combination.
- **PII (non-patient-sensitive but still protected)** in a healthcare system: clinician/staff personal details, fee structures + payout amounts, salary/bank details, vendor payment info.
- **Tag at the schema level** so classification is auditable: `COMMENT ON COLUMN patients.dob IS 'PHI: date_of_birth';` etc. A schema with no PHI tagging is a gap.

### Access control - Row-Level Security (RLS) as the default for multi-tenant clinical data
- Enable RLS on every PHI/PII table; scope reads by facility/assignment, not application logic.
- **Cross-facility isolation** is a named, testable control: a doctor at Facility A querying Facility B patients must return 0 rows.
- Audit log table is **insert-only and tamper-proof** (no UPDATE, no DELETE policy).
- **Never use the service-role key in client code** - use the anon/publishable key and let RLS enforce. Service-role-in-client is a P0 audit-blocker.

### Audit trail (every PHI access OR modification)
Log: timestamp, user_id, patient_id, action (create/read/update/delete/print/export), resource type + id, before/after on changes, ip, session. This IS the HIPAA accounting-of-disclosures evidence.

### Common leak vectors (the PHI red-flag checklist - audit code for these)
- PHI in **error messages / stack traces** sent to the client (log server-side with opaque IDs only).
- PHI in **console/log output** (never log full patient objects; opaque UUIDs only, not MRNs/national IDs/names).
- PHI in **URL parameters** (query strings + path segments leak into logs + browser history).
- PHI in **browser storage** (localStorage/sessionStorage) - keep PHI in memory only, fetch on demand.
- **service_role key** in client-side code.
- Unsanitized stack traces shipped to error-tracking SaaS.

### PHI deployment checklist (pre-deploy gate, every release)
No PHI in error messages/stack traces, console, URLs, or browser storage. No service-role key in client code. RLS on all PHI/PII tables. Audit trail on all modifications. Session timeout configured. API auth on all PHI endpoints. Cross-facility isolation verified.

---

## 3. EMR/EHR clinical-safety patterns (healthcare-emr-patterns)

The governing question on every design decision: **"Could this harm a patient?"**

- **Single-page vertical encounter flow** (no tab-switching that fragments the clinical workflow): sticky patient header (demographics, allergies, active meds) over a vertical scroll - complaint -> HPI -> exam -> vitals -> diagnosis (ICD-10/SNOMED) -> meds (drug DB + interaction check) -> investigations -> plan -> sign/lock/print.
- **Smart templates** carry `redFlags[]` that trigger a **visible, non-dismissable alert - never a toast.**
- **Locked encounter pattern:** once signed, no edits - only an **addendum** as a separate linked record; both appear in the timeline; audit captures who signed + when. (This is also the HIPAA amendment mechanism.)
- **Clinical UI rules** (stricter than typical web): WCAG AA 4.5:1 contrast, 44x44px touch targets, full keyboard nav, **no color-only indicators** (pair color with text/icon), screen-reader labels, **no auto-dismissing toasts for clinical alerts.**
- **Anti-patterns:** clinical data in localStorage; silent failures in interaction checking; dismissable toasts for critical alerts; tab-based encounter UIs; edits to locked encounters; clinical data without audit trail; `any` type for clinical structures.

---

## 4. CDSS safety (healthcare-cdss-patterns) - zero tolerance for false negatives

CDSS = patient-safety-critical. Build the engine as a **pure function library, zero side effects** (fully testable). Three core modules:
1. `checkInteractions(newDrug, currentMeds, allergies)` -> severity-sorted alerts. **Interaction pairs MUST be bidirectional** (A-B implies B-A).
2. `validateDose(drug, dose, route, weight, age, renalFunction)` -> validation result. **If a rule needs weight and weight is missing, BLOCK - never pass.** Same for age/renal/absolute-max brackets.
3. `calculateNEWS2(vitals)` (and qSOFA/APACHE/GCS) -> score + risk + escalation. **Scoring tables must match the published spec exactly** (e.g. Royal College of Physicians for NEWS2).

### Medication safety flow
Select drug -> check current meds -> check encounter meds -> check allergies -> validate dose vs weight/age/renal -> **CRITICAL interaction BLOCKS prescribing by default**; clinician must document an override reason stored in the audit trail. MAJOR -> warning + required acknowledgment. The system **never silently allows a critical interaction.**

### Alert severity -> UI behavior (the contract)
| Severity | UI | Clinician action |
|---|---|---|
| Critical | Block. Non-dismissable modal. Red. | Document override reason to proceed |
| Major | Inline warning banner. Orange. | Acknowledge before proceeding |
| Minor | Inline info note. Yellow. | Awareness only |

Critical alerts are **never toasts and never auto-dismissed.** Override reasons always land in the audit trail.

### CDSS anti-patterns
Optional/skippable checks without documented reason; interaction checks as toasts; `any` types for clinical data; hardcoded interaction pairs vs a maintainable data structure; silently caught CDSS errors (must surface loudly); skipping weight-based validation when weight absent (must block).

---

## 5. EMR/EHR interoperability compliance (HL7 / FHIR)

Healthcare software rarely lives alone - it integrates with hospital systems. Interop is a named compliance surface, tested as a HIGH gate:
- **HL7 v2.x message parsing** (ADT, ORM, ORU etc.) - tested including **malformed-message handling** (must fail loudly, never silently mis-map).
- **FHIR resource validation** (R4 resources - Patient, Encounter, Observation, MedicationRequest etc.) against the spec.
- **Lab result mapping** into the clinical model with reference-range highlighting + critical-value non-dismissable alerts.
- Diagnosis/medication coding via standard terminologies: **ICD-10 / SNOMED CT** (diagnoses), drug DB for meds.
- Treat every interop endpoint that carries PHI as in-scope for the PHI checklist (auth, audit, no PHI in URLs/logs).

---

## 6. Patient-safety deployment gate (healthcare-eval-harness) - the CI gate

A single CRITICAL failure **blocks deployment.** Patient safety is non-negotiable. Five categories, run in order; framework-agnostic (Jest/Vitest/pytest/PHPUnit - thresholds are the constant).

| Category | Threshold | On failure |
|---|---|---|
| CDSS Accuracy (interaction pairs both directions, dose rules, scoring vs spec, no false negatives) | **100%** | BLOCK deploy |
| PHI Exposure (error responses, console, URLs, browser storage, cross-facility isolation, unauth access, service-role-key absence) | **100%** | BLOCK deploy |
| Data Integrity (locked encounters, audit entries, cascade-delete protection, concurrent edits, no orphans) | **100%** | BLOCK deploy |
| Clinical Workflow (encounter lifecycle, templates, med sets, search, prescription PDF, red-flag alerts) | 95%+ | WARN, allow with review |
| Integration Compliance (HL7 parse, FHIR validation, lab mapping, malformed handling) | 95%+ | WARN, allow with review |

- CRITICAL gates run with `--bail` (stop on first failure) and enforce coverage thresholds.
- **Eval anti-patterns:** skipping CDSS tests "because they passed last time"; CRITICAL thresholds below 100%; `--no-bail` on CRITICAL suites; mocking the CDSS engine in integration tests (must test real logic); deploying when the gate is red; running CDSS suites without coverage.
- Pin CI actions by **commit SHA, not floating tags** (fleet doctrine - the harness example uses `@v4` tags; SHA-pin them in any pipeline we author).
- Output is an **eval report** per commit (category / tests / pass / fail / status + coverage + SAFE-TO-DEPLOY verdict) - this doubles as audit evidence that the patient-safety gate ran green for the release.

---

## 7. How this plugs into the existing engagement machinery

- **Intake:** when the client profile shows PHI or a healthcare sector, add: covered-entity vs business-associate posture, BAA chain status (client + every subprocessor/LLM), EMR/EHR systems to integrate (HL7/FHIR), and whether a CDSS module is in scope (raises the engagement to patient-safety-critical).
- **Gap matrix:** reuse the existing TSC/Annex-A row shape. HIPAA Security Rule technical safeguards, the PHI deployment checklist, and the eval-harness categories all become rows with owner + evidence source. PHI-in-code findings are P0 audit-blockers.
- **Evidence:** the audit trail, RLS policy exports, and the green eval report ARE the evidence - they slot into the evidence-by-control-objective program already defined.
- **Readiness report:** add a Healthcare/PHI section to the white-label report (PHI checklist status, BAA chain, patient-safety gate verdict) using the existing Policies/Evidence/Monitoring shape.
- **Boundaries unchanged:** legal interpretation of HIPAA/BAA terms -> legal-advisor; exploit-side control testing -> security-auditor; the actual code implementation -> cto/engineering (we define + evidence the controls, the patient-safety gate is run by/with devops).

## Source ledger
- ECC repo: affaan-m/ECC (MIT). Skills read 2026-06-14 via raw.githubusercontent.com (branch main): skills/healthcare-emr-patterns, skills/healthcare-cdss-patterns, skills/healthcare-phi-compliance, skills/hipaa-compliance, skills/healthcare-eval-harness, agents/healthcare-reviewer.md. Clinical methodology origin: Dr. Keyur Patel, Health1 Super Speciality Hospitals. Methodology absorbed; no source code bundled into this employee.
