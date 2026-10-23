# Original ten-implementation roadmap

Current as of 2026-10-24. The original roadmap ends at 10; open maintenance does
not imply authorization to start another implementation.

| Milestone | Delivered scope | Status/document |
| --- | --- | --- |
|01|Separate local infrastructure|Accepted; [01](implementation-01.md)|
|02|Business APIs and data contracts|Accepted; [02](implementation-02.md)|
|03|Deterministic support workflow|Accepted; merged historical checkpoint 1489752; [03](implementation-03.md)|
|04|Bounded local Ollama advice|Accepted; [04](implementation-04.md)|
|05|Human review and Next.js dashboard|Accepted; [05](implementation-05.md)|
|06|Lead intake and deduplication|Accepted; checkpoint 29aa141; [06](implementation-06.md)|
|07|Daily operations digest|Accepted; checkpoint e746ff6; [07](implementation-07.md)|
|08|Resilience and recovery|Accepted; checkpoint 973c408; [08](implementation-08.md)|
|09|Testing and security boundaries|Accepted with documented exceptions; checkpoint 64f7a47; [09](implementation-09.md)|
|10|Developer handoff and portfolio evidence|Accepted with documented exceptions; final portfolio release; [10](implementation-10.md)|

The authorized final release integrates Implementations 07–10 into `main` by
fast-forward from the previously published 29aa141 checkpoint. Separate
implementation branches and commits are retained; consult Git history for the
final tip SHA. No release tag is created. Earlier reports preserve their
historical pre-checkpoint status; this index and the handover provide current status.

## Reading paths

- Recruiter: [README](../README.md) → [presentation/CV](portfolio-presentation.md).
- Developer: [setup](developer-setup.md) → [architecture](architecture.md) →
  [demos](portfolio-demos.md) → [handover](codex-handover.md).
- Reviewer: [benchmark](benchmark-report.md) → [security](security-review.md) →
  [exception investigation](implementation-09-exception-review.md) →
  [recovery runbook](recovery-runbook.md).
- Maintainer: all seven [open follow-ups](implementation-09.md#m-open-security-and-maintenance-follow-ups).

## Accepted exceptions and open work

| Stable ID | Still open |
| --- | --- |
|FF09-SEC-01|Qualify platform/runtime image patches, including n8n bundled Node|
|FF09-HIST-01|Supported history retention/compaction controls and protected backup policy|
|FF09-INGRESS-01|Sender authentication and resource limits for legacy ingress|
|FF09-TEST-01|Resolve pytest dependency advisory through compatible maintenance|
|FF09-AUTH-01|Session lifecycle, TLS and identities beyond shared local reviewer|
|FF09-REC-01|Remaining normal/n8n restore, ownership and host reboot drills|
|FF09-BUILD-01|Build/image reproducibility and patching|

Five absent historical autosaves, critical/high image findings and legacy
unauthenticated ingress remain accepted risks **only for trusted-local development**.
Implementation 10 does not resolve them or authorize public production.
Protected encrypted evidence remains outside Git. Maintenance, commit and
publication need separate instructions.
