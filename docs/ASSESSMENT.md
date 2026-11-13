# Life and protection AI value-chain assessment

Simulated scenario · synthetic data · illustrative, not legal advice

Simulated UK life and protection insurer · UK · GBP · Individual life, Group life & disability, Income protection, Annuities

Use cases assessed: 14 · Eligible at Medium appetite: 11 · Shortlisted: 5 · Not eligible: 3

## Context

Simulated UK life and protection insurer operates in UK; the assessment covers 14 use cases across 5 value-chain stages: Distribution, Underwriting, Policy admin, Servicing, Claims.  
Lines in scope: Individual life, Group life & disability, Income protection, Annuities; currency: GBP.  
Each use case passes an internal AI risk gate before it is ranked, using the selected appetite and weighted assessment criteria.  
2 use cases include a worked governance pack with controls trace and agent accountability.  
The internal AI risk tier is an internal appetite measure, not a regulatory classification.

## Stage × internal risk tier counts

| Stage | Low | Medium | High | Unacceptable |
| --- | --- | --- | --- | --- |
| Distribution | 1 | 1 | 0 | 0 |
| Underwriting | 1 | 1 | 1 | 1 |
| Policy admin | 1 | 3 | 0 | 0 |
| Servicing | 0 | 2 | 0 | 0 |
| Claims | 0 | 1 | 1 | 0 |

## Scoring formula

Gate: eligible only when internal AI risk tier ≤ appetite (Medium); unacceptable is never eligible.
Score = round(100 × (5 × value + 3 × feasibility + 2 × data readiness) ÷ (5 × 10), 1).
Tie-break: value descending, data readiness descending, then use case ID ascending.

## Ranked use cases

| Rank | ID | Use case | Stage | Line | Value | Feasibility | Data readiness | Internal AI risk tier | Score | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [VC-01](#vc-01) | Underwriting Evidence Summariser | Underwriting | Individual Life | 4 | 4 | 3 | Medium | 76.0 | Shortlisted |
| 2 | VC-09 | Adviser Quote and Illustration Assistant | Distribution | Individual Life | 3 | 5 | 4 | Low | 76.0 | Shortlisted |
| 3 | VC-13 | Death and Income-Protection Claim Document Intake | Claims | All | 4 | 4 | 2 | Medium | 72.0 | Shortlisted |
| 4 | [VC-05](#vc-05) | Policy-Admin Data Exception Agent | Policy admin | All | 4 | 3 | 3 | Medium | 70.0 | Shortlisted |
| 5 | VC-11 | Retention and Lapse Propensity Insight | Servicing | All | 3 | 4 | 4 | Medium | 70.0 | Shortlisted |
| 6 | VC-07 | Policy Alteration Triage | Policy admin | Individual Life | 3 | 4 | 3 | Medium | 66.0 | Eligible |
| 7 | VC-06 | New Business Document Completeness Check | Policy admin | All | 2 | 5 | 4 | Low | 66.0 | Eligible |
| 8 | VC-10 | Group Scheme Quote and Renewal Pricing Support | Distribution | Group Life & Disability | 4 | 2 | 3 | Medium | 64.0 | Eligible |
| 9 | VC-12 | Annuity Payment and Existence-Check Exception Review | Servicing | Annuities | 3 | 3 | 3 | Medium | 60.0 | Eligible |
| 10 | VC-04 | Underwriting Rules Guidance Assistant | Underwriting | All | 1 | 5 | 5 | Low | 60.0 | Eligible |
| 11 | VC-08 | Closed-Book Legacy Policy Data Remediation | Policy admin | All | 4 | 2 | 1 | Medium | 56.0 | Eligible |

## Not eligible

| ID | Use case | Stage | Internal AI risk tier | Status |
| --- | --- | --- | --- | --- |
| VC-02 | Automated Underwriting Acceptance with Premium Loadings | Underwriting | High | Not eligible – internal risk tier above appetite |
| VC-03 | Automated Decline of Life Applications from Medical Evidence | Underwriting | Unacceptable | Not eligible – ruled unacceptable |
| VC-14 | Claims Fraud Indicator Scoring | Claims | High | Not eligible – internal risk tier above appetite |

## Worked governance

### VC-01 · Underwriting Evidence Summariser · Underwriting · Medium risk tier

Summarises application disclosures and medical evidence into a structured summary with page citations for an underwriter, who makes every decision; it never sets terms, exclusions or premium.

**Owner role:** Underwriting Operations Lead

Pass: 9 · Fail: 1 · Not tested: 2 · Exceptions: 1

#### Controls trace

| Control ID | Family | Requirement | Control description | Owner role | Evidence | Result | Exception | Review date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CT-VC-01-01 | Customer Outcomes | The summariser must support the underwriter's decision without ever accepting a risk, declining an application or setting terms, exclusions or premium. | The output is a cited evidence summary only; the interface has no accept, decline or rate-setting action, and the underwriting decision system rejects any term write from the summariser service identity. The Underwriting Operations Lead reviews the interface and permissions quarterly. | Underwriting Operations Lead | [Design record](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) | pass | – | 2026-09-01 |
| CT-VC-01-02 | Model Risk | The accuracy of each summary must be measured against a sample verified by an underwriter. | Each month, 150 randomly selected summaries are checked fact by fact against the source pack by an underwriter; fact-level accuracy must be at least 95% and citation completeness 100%, with any miss logged and root-caused within 10 working days. | Model Risk Manager | **Simulated evidence** — Interim 150-summary accuracy report showing fact-level misses, Sep 2026 (simulated) | fail | Correct the extraction errors found, add them to the regression set and re-run the monthly 150-summary accuracy sample by January 2027. | 2026-09-01 |
| CT-VC-01-03 | Data Protection | Only the health information needed to assess the application may be processed, and only underwriting roles may see it. | The summariser ingests only the application, medical evidence and consent fields listed in the approved data map; it masks identifiers not needed for assessment. Access is limited to the underwriting role group, recertified quarterly and access logs are reviewed monthly by the Underwriting Data Protection Lead. | Underwriting Data Protection Lead | **Simulated evidence** — Approved data map, role access list and quarterly recertification, Sep 2026 (simulated) | pass | – | 2026-09-08 |
| CT-VC-01-04 | Access Control | The summariser must have read-only access to the evidence store and no way to write to the underwriting decision system. | Its service identity holds read-only scope on the evidence store; a deployment test proves no write permission or API route exists to the decision system, and any failed test blocks release. The Underwriting Platform Lead reviews the permission set quarterly. | Underwriting Platform Lead | [Design record](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) | pass | – | 2026-09-08 |
| CT-VC-01-05 | Record Keeping | Each underwriting decision must leave a retrievable record of who decided, what was decided, which summary version was used and which evidence pages were relied on. | The decision log writes underwriter role and identifier, decision, summary version and cited evidence pages in one immutable entry; entries are retained for seven years and reconciled monthly to completed decisions by the Underwriting Operations Manager. | Underwriting Operations Manager | [Design record](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) | pass | – | 2026-09-15 |
| CT-VC-01-06 | Model Risk | Every fact in a summary must point to the page it came from, and an uncited fact must not reach the underwriter. | A pre-release rule blocks the summary if any extracted fact lacks a page citation or the cited page is missing from the pack; 100% of summaries are checked by the rule, 50 per month are manually sampled, and the Model Risk Manager reviews the results monthly. | Model Risk Manager | **Simulated evidence** — Citation gate test results and 50-summary manual sample, Sep 2026 (simulated) | pass | – | 2026-09-15 |
| CT-VC-01-07 | Change Management | Changes to prompts, models or extraction rules must be regression tested and approved before release. | Every change requires peer review, a run against a 200-case underwriter-adjudicated set, fact accuracy of at least 95%, citation completeness of 100% and change board approval; rollback is rehearsed and release is blocked on a failed threshold. The Underwriting Change Manager maintains the record. | Underwriting Change Manager | **Simulated evidence** — Change board approval and 200-case regression results, Sep 2026 (simulated) | pass | – | 2026-09-22 |
| CT-VC-01-08 | Operational Resilience | Underwriting must continue if the summariser is unavailable. | A documented manual underwriting queue with trained staff, a four-hour recovery objective and a monthly failover test; the Underwriting Operations Lead reviews test results and any backlog at each monthly service review. | Underwriting Operations Lead | **Simulated evidence** — Monthly failover test log and fallback queue procedure, Sep 2026 (simulated) | pass | – | 2026-09-22 |
| CT-VC-01-09 | Customer Outcomes | Complex applications and disclosures indicating vulnerability must go to a senior underwriter. | Rules flag applications above the agreed complexity threshold or with a vulnerability indicator, route them to a senior underwriter within 15 minutes and require recorded senior sign-off before any decision; the Senior Underwriting Manager reviews the routing log weekly. | Senior Underwriting Manager | **Simulated evidence** — Complexity and vulnerability routing log with senior sign-off, Sep 2026 (simulated) | pass | – | 2026-09-29 |
| CT-VC-01-10 | Model Risk | Underwriter edits and overrides of summaries must be monitored for patterns that suggest the summariser is misleading them. | A monthly dashboard reports edit rate, override rate and override reasons by underwriter team and evidence type; a rate above 10% or three linked complaints triggers a root-cause review within 10 working days, owned by the Underwriting Quality Lead. | Underwriting Quality Lead | **Simulated evidence** — Monitoring dashboard specification and proposed edit metrics, Sep 2026 (simulated) | not tested | – | 2026-09-29 |
| CT-VC-01-11 | Data Protection | Copies of medical evidence held by the summariser must be kept only as long as needed and then deleted. | Evidence copies and cached extracts are deleted automatically after 30 days, deletion is attested monthly and a quarterly sample confirms no orphaned copies remain; any retention exception needs approval from the Underwriting Data Protection Lead. | Underwriting Data Protection Lead | **Simulated evidence** — 30-day deletion attestation and quarterly orphan-copy sample, Sep 2026 (simulated) | pass | – | 2026-10-06 |
| CT-VC-01-12 | Customer Outcomes | Underwriters must be trained on what the summariser can and cannot do before they rely on it. | Role-based training with a scenario assessment must be completed before system access, refreshed annually and rechecked on role change; completion is recorded against each underwriter role by the Underwriting Training Lead. | Underwriting Training Lead | **No evidence – exception** — Underwriter training completion record - not yet attached, Oct 2026 (simulated) | not tested | EX-01 | 2026-10-06 |

#### Agent accountability

| Action | Agent allowed | Tool permissions | Accountable human role | Escalation path | Log field |
| --- | --- | --- | --- | --- | --- |
| Recommend | yes | read-only: application disclosures, medical evidence pages, underwriting rules library | Underwriter | Underwriter → Senior underwriter | summary_version |
| Approve | no | no agent permission; decision approval held by the underwriter in the underwriting decision record | Underwriter | Underwriter → Senior underwriter | underwriter_decision_id |
| Execute | no | no agent write; permission to apply terms in the underwriting system held by the senior underwriter | Senior underwriter | Senior underwriter → Chief underwriter | execution_id |
| Override | no | no agent permission; override authority held by the chief underwriter under the documented underwriting exception process | Chief underwriter | Chief underwriter → Underwriting governance forum | override_reason_code |
| Stop | yes | read-only: application disclosures, medical evidence pages, underwriting rules library; agent may halt the summary and escalate when evidence is missing, illegible or conflicting | Underwriter | Underwriter → Senior underwriter | stop_reason_code |

### VC-05 · Policy-Admin Data Exception Agent · Policy admin · Medium risk tier

Flags conflicting policy records, including benefit amount mismatches, lapsed policies still collecting premium, commission split errors and conflicting life-assured details after a platform migration, and recommends an evidence-backed correction for a policy data owner to approve without writing to the policy administration system.

**Owner role:** Policy Administration Data Owner

Pass: 8 · Fail: 2 · Not tested: 2 · Exceptions: 1

#### Controls trace

| Control ID | Family | Requirement | Control description | Owner role | Evidence | Result | Exception | Review date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CT-VC-05-01 | Access Control | The policy-admin agent must have read-only identity and no way to write to the policy administration system. | The agent runs under a read-only service identity scoped to the replicated policy data; role permissions omit write, update and delete, and a quarterly access test proves no write path before each release. The Policy Administration Platform Lead owns the test. | Policy Administration Platform Lead | [Design record](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) | pass | – | 2026-10-13 |
| CT-VC-05-02 | Record Keeping | Every recommendation must identify the conflicting records and the rule it applied. | A pre-approval check blocks a recommendation unless it lists the conflicting record identifiers, the policy version, the rule identifier and links to the source records; 100% of open recommendations are tested monthly by the Policy Data Governance Lead. | Policy Data Governance Lead | **Simulated evidence** — Citation completeness test showing uncited recommendations, Sep 2026 (simulated) | fail | Backfill citations for all open recommendations and enable the pre-approval citation block by January 2027. | 2026-10-13 |
| CT-VC-05-03 | Model Risk | Matching thresholds for migrated records must be calibrated on a labelled sample so genuine matches are found without merging unrelated policies. | Thresholds are recalibrated quarterly against a labelled sample of at least 300 migrated record pairs; precision must be at least 95% and recall at least 90%, with model owner approval for every threshold change recorded by the Policy Data Science Lead. | Policy Data Science Lead | **Simulated evidence** — Calibration report showing precision below the 95% threshold, Sep 2026 (simulated) | fail | Recalibrate the migrated-record matching thresholds on the current labelled sample and record model owner approval by February 2027. | 2026-10-20 |
| CT-VC-05-04 | Model Risk | The rules that resolve known policy conflicts must be regression tested on every release. | A regression suite of at least 250 adjudicated conflicts runs on every release; rule-level precision and recall are reported to the Policy Data Science Lead, and a failed case blocks deployment until the policy data owner signs off. | Policy Data Science Lead | **Simulated evidence** — 250-case rule regression results and release sign-off, Sep 2026 (simulated) | pass | – | 2026-10-20 |
| CT-VC-05-05 | Customer Outcomes | No premium, benefit or payee change may be made without approval from the policy data owner. | Recommendations remain advisory; premium, benefit and payee fields can only be changed through an approval step restricted to the policy data owner role, and approval is written to the immutable log before any update is applied. | Policy Administration Data Owner | [Design record](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) | pass | – | 2026-10-27 |
| CT-VC-05-06 | Operational Resilience | If the agent or its data feed fails, an independent daily reconciliation must still find conflicting policy records. | An independent reconciliation job runs daily against source and migrated records, a backlog alert fires at 24 hours, and a manual conflict review procedure is tested quarterly with results logged and reviewed by the Policy Administration Resilience Lead. | Policy Administration Resilience Lead | **Simulated evidence** — Daily independent reconciliation output and quarterly manual test log, Oct 2026 (simulated) | pass | – | 2026-10-27 |
| CT-VC-05-07 | Data Protection | Only the policy and life-assured fields needed for the review may be exposed, and every access must be logged. | An allow-list exposes only in-scope policy, benefit and life-assured fields; free-text notes are excluded, queries are written to a tamper-evident access log retained for 12 months, and the Policy Data Protection Lead reviews access quarterly. | Policy Data Protection Lead | **Simulated evidence** — Field allow-list, access log extract and quarterly review, Oct 2026 (simulated) | pass | – | 2026-11-03 |
| CT-VC-05-08 | Change Management | Changes to conflict detection logic or the agent's tool permissions must be approved and regression tested. | Every change needs change board approval, a full regression run and a versioned permission diff; emergency changes are reviewed within five working days, a failed regression blocks release, and the Policy Administration Change Manager retains the record. | Policy Administration Change Manager | **Simulated evidence** — Change board approval, regression results and permission diff, Oct 2026 (simulated) | pass | – | 2026-11-03 |
| CT-VC-05-09 | Record Keeping | Each approval must be recorded in an immutable log showing the recommendation, approver role, decision and time. | An append-only approval log captures recommendation identifier, approver role, decision, rationale and timestamp; it is retained for seven years and reconciled monthly to the recommendation list by the Policy Data Governance Lead. | Policy Data Governance Lead | [Design record](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) | pass | – | 2026-11-10 |
| CT-VC-05-10 | Access Control | Only the policy data owner role may approve a recommendation, and the agent must not approve its own work. | Approval is restricted to the policy data owner role by role-based access; the agent identity has no approval permission, and a quarterly separation-of-duties test confirms it cannot approve its own recommendation. The Policy Administration Platform Lead owns the test. | Policy Administration Platform Lead | [Design record](https://github.com/kakali-bandyopadhyay/life-ai-value-chain/blob/main/data/agent_accountability.json) | pass | – | 2026-11-10 |
| CT-VC-05-11 | Model Risk | The agent's conflict types and the rate at which its recommendations are accepted must be monitored for drift. | A monthly dashboard tracks conflict volume by type, approval rate and override reasons against agreed tolerances; drift beyond tolerance opens a model review within 10 working days, owned by the Policy Data Science Lead. | Policy Data Science Lead | **Simulated evidence** — Drift monitoring dashboard specification and metric definitions, Nov 2026 (simulated) | not tested | – | 2026-11-12 |
| CT-VC-05-12 | Customer Outcomes | Approvers must be trained on the agent's limits and on escalating conflicts that affect customers. | Role-based training with a scenario assessment is completed before approval access, refreshed annually and rechecked on role change; completion is recorded against the approver role by the Policy Administration Training Lead. | Policy Administration Training Lead | **No evidence – exception** — Approver training completion record - not yet attached, Nov 2026 (simulated) | not tested | EX-02 | 2026-11-12 |

#### Agent accountability

| Action | Agent allowed | Tool permissions | Accountable human role | Escalation path | Log field |
| --- | --- | --- | --- | --- | --- |
| Recommend | yes | read-only: policy schedule, policy admin record, premium collection status, commission split | Policy data owner | Policy data owner → Policy administration manager | recommendation_id |
| Approve | no | no agent write; correction approval held by the policy data owner in the policy correction approval queue | Policy data owner | Policy data owner → Policy administration manager | approved_at |
| Execute | no | no agent write; policy administration system write permission held by the policy administration manager | Policy administration manager | Policy administration manager → Head of policy administration | policy_record_update_id |
| Override | no | no agent permission; override authority held by the head of policy administration under the documented policy administration exception process | Head of policy administration | Head of policy administration → Policy administration governance forum | override_authorised_by |
| Stop | yes | read-only: policy schedule, policy admin record, premium collection status, commission split; agent may halt the correction and escalate when evidence is missing, illegible or conflicting | Policy data owner | Policy data owner → Policy administration manager | stop_reason_code |

---

Synthetic and illustrative. The internal AI risk tier is not a regulatory classification. This material needs Legal/Compliance validation, is not production-ready, and is not any firm's policy.

MIT licence
