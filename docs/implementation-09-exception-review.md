# Implementation 09 — Final acceptance exception investigation

Reviewed **2026-10-24, Asia/Kolkata**. Recommendation:
**ACCEPT WITH DOCUMENTED EXCEPTIONS**, limited to the existing trusted-local
development/portfolio scope. The user explicitly granted this limited final
acceptance on **2026-10-24 (Asia/Kolkata)**.

The three exceptions are accepted risks, **not resolved vulnerabilities**. This
acceptance authorizes no Git commit, push, merge, public production deployment
or original-service changes. No unconditional security certification or wider
exposure is recommended. The investigation findings below remain preserved;
outstanding work is tracked in the
[open follow-up register](implementation-09.md#m-open-security-and-maintenance-follow-ups).

The original 41-file proposal was reviewed. No runtime source/configuration or
workflow correction was necessary for this investigation. Existing application
hardening remains useful and the selected checks passed again. No service/image
was replaced. High-impact vendor findings remain priorities for separately
qualified maintenance; package presence was not treated as proof of exploitability.

Evidence: [investigation JSON](evaluation/implementation-09-exception-review.json),
[per-finding catalog](evaluation/implementation-09-vulnerability-triage.json),
[original full test report](implementation-09.md).

## 1. Historical workflow differences

### Confirmed observations

Fresh supported `n8n export:entities --includeExecutionHistoryDataTables=true`
was privately compared with the retained encrypted Implementation 07 export.
Decryption occurred only in memory inside FlowForge n8n; secret/plaintext payloads
were not printed or committed. The five absent rows are:

| Version ID | Workflow | Created UTC | Nodes |
| --- | --- | --- | ---: |
| 0af19eca-793b-45ec-bb0e-e936e11b3824 | Support | 2026-10-22T14:56:59.757Z | 24 |
| 99e612d2-7ebb-40b4-9de2-0f059155f188 | Support | 2026-10-22T14:57:06.038Z | 11 |
| 7873bb0c-b7a0-4cc0-a347-10f218f135aa | Support | 2026-10-22T14:57:34.608Z | 13 |
| f4b701da-a9f1-40e2-a52b-6db91f3e9bec | Support | 2026-10-22T14:57:50.202Z | 13 |
| ef9cdd3c-c544-43d4-93a8-27f7abdf550a | Digest | 2026-10-23T14:24:08.013Z | 5 |

All five were autosaved and none appears in the retained publication history.
The first was a 24-node intermediate draft; it must not be imported as the live
13-node support workflow.

Current supported exports still contain **nine identical history rows**. Retained
execution entities/data are **335/335**, encrypted credentials **1**, publication
history **21**; all match by row hash. Seven current complete workflow definitions
match the pre-09 baseline; three published support/lead/digest workflows match
source at 13/11/5 nodes. Four drafts remain inactive. Failure simulation is false.

### Installed mechanisms and offline evidence

Two independent mechanisms exist in installed n8n 2.43.8:

1. Recent-history compaction runs hourly/on startup, with a default 15-minute
   minimum age and two-hour window. It merges additive edits, preserving named/
   published versions, differing authors and changes over 20 minutes apart.
2. Community age pruning defaults to **24 hours**. Configured pruneTime=-1 does
   not override a finite license limit: the helper selects the license limit.
   There is no stored license certificate or environment license override.
   The repository excludes current, active, previously published and open-review
   pinned versions when deleting old rows. This is unrelated to
   `EXECUTIONS_DATA_PRUNE=false`.

Replaying the **actual installed pure grouping functions** over the encrypted
export's rows in memory selected three missing support autosaves and the missing
digest autosave. It **did not select the earliest 24-node support draft**, because
the subsequent version removes nodes. A separate offline age-eligibility check
at the pre-09 baseline time selected all four unpublished support autosaves,
including that draft. Together these mechanisms account for eligibility of all
five missing rows. No repository delete/prune method was invoked.

The retained export file mtime is October 23 14:43 UTC, before the support drafts
reached 24 hours around 14:57 UTC. File mtime is supporting context, not an
authenticated event record. No matching compaction/pruning marker was found in
retained normal logs or four n8n event logs, and the fresh pre-09 baseline lacks
version-history rows.

**Conclusion:** automatic compaction plus Community age pruning is a strongly
supported explanation. Exact task execution, removal time and historical actor
cannot be proven. Compaction alone is an incomplete explanation. No finding of
unauthorized workflow editing is established by these differences.

### Preservation action and remaining risk

Both the older and fresh encrypted entity archives were copied into a new
0700 directory under `/home/adnan/.local/share/flowforge-ai/backups/`, files0600,
with SHA256 evidence. Copies preserve all five absent definitions outside
ephemeral /tmp. Paths/hashes are in the investigation JSON; backups stay outside
Git. Matching existing encryption key/configuration remains private and unchanged.

No workflow/history/credential/volume was reset, recreated, restored, imported,
deleted or modified. In-database historic autosaves remain absent. The continuing
risk is **Medium operational**: the running Community retention policy can remove
other unpublished versions. Export before future maintenance/authoring and adopt
an explicit protected backup policy. Changing retention, edition/license or
restoring any historic version requires a separately reviewed plan; do not
promise that a single prune-time variable disables every mechanism.

## 2. Image vulnerability assessment

All prior raw report hashes and exact local image IDs were revalidated; the
images did not change. The full Scout scan was **not rerun** during this
investigation. The October 23 findings remain visible without suppression:

| Image | Critical | High |
| --- | ---: | ---: |
| Backend | 0 | 1 |
| Frontend | 0 | 0 |
| n8n | 9 | 46 |
| PostgreSQL | 4 | 32 |

The catalog below enumerates **92 critical/high rule rows, 90 unique IDs**,
including package, installed version, scanner fix version and individual
precondition/status. All scanner ratings are retained even where vendor severity
differs. This is static configuration/data-flow assessment, not exploit execution
or an exhaustive signed VEX determination.

Primary records were checked in the CNA-maintained CVEProject dataset, upstream
MCP/Nodemailer advisories and vendor release/security records. For the two MCP
CVEs unavailable through CVE JSON endpoints, upstream advisories were read
directly. The JSON retains primary fix ranges, artifact locations and rationale.
Scanner version advice can simplify multi-package/branch ranges; the SDK fix for
CVE-2026-111768 is **1.32.0**, while server fix is **2.3.0**, and input-element
limits must also be enabled.

### What the evidence establishes

- **PostgreSQL Go findings (34 rows):** all map to `/usr/local/bin/gosu`, version
  1.19 built with Go1.24.6. Its SHA256 exactly matches the upstream release.
  ELF symbols include the positive control `os/exec.LookPath`; no CNA-listed
  affected function symbol matched. Affected HTTP/TLS/X509/mail/XML/ASN.1/URL/
  os.Root APIs are outside gosu's reviewed privilege-switch/exec source path.
  Windows-specific findings additionally lack the platform precondition.
  gosu replaces itself with postgres and is not a resident network server.
  This is strong evidence of no affected path in this binary, not a claim that
  an old Go version is generally safe. Symbol absence alone is insufficient
  (inlining exists); source/package context supports the result. **govulncheck
  was not run**, and none of these findings was hidden from the scan.
- **PostgreSQL native libxml2/zlib:** the libraries are linked. Current backend
  queries do not invoke SQL XML/DTD validation or nonblocking gz* printf writes.
  Trusted direct SQL/XML users are a different surface. The libxml2 branch has
  no scanner fixed package; upstream fix is 2.15.4. Use vendor maintenance rather
  than altering the running database.
- **Backend zlib:** runtime1.3.1 and Debian package
  1:1.3.dfsg+really1.3.1-1. Debian still marks it unfixed, while upstream says the
  relevant nonblocking support began in1.3.1.2. This range disagreement is
  explicitly retained. No nonblocking gzwrite→gzprintf path exists in reviewed
  application code. Do not declare a false positive solely from the number.
- **n8n feature libraries:** no Git, Handlebars AST, email, TOML, HEVC or native
  PCRE2 input path exists in the three fixed workflows. MCP is disabled (setting
  absent defaultsfalse; HTTP endpoint404), and its controller has enabled/auth
  guards. The per-request server factory also avoids the shared MCP server
  pattern. This conclusion does not cover arbitrary future editor workflows.
- **n8n tooling copies:** brace-expansion, undici6.28.0 and
  http-cache-semantics4.2.0 findings locate under global npm/node_modules.
  Production starts n8n directly and never feeds customer input to that tooling.
  The bundled Node runtime is separate and must be reviewed independently.
- **n8n libcurl/OpenSSL:** libraries are installed; curl CLI is absent. Current
  HTTP Request nodes use the Node/axios stack and fixed plain-HTTP backend URLs.
  Specific QUIC/DTLS/RPK/CMP/CMS/empty-AEAD and libcurl option preconditions are
  not configured. Node TLS still exists for other runtime features; do not turn
  this result into a blanket platform safety claim.
- **n8n Brotli/Node is the maintenance priority:** Node26.7.0 and bundled
  Brotli1.2.0 predate CVE-2026-111497 fixes. The current intake parser handles
  gzip/deflate, with **no br decoding branch**, but outgoing Node clients can
  decompress responses. Current workflows use trusted fixed backend destinations;
  no anonymous exploit path was demonstrated. Broader editor/runtime fetch paths
  are not exhaustively excluded. The potential impact remains **High**
  (scannerCritical). Upgrading APK Brotli alone does not fix bundled Node.
- **Frontend Node22.23.4 already contains the Brotli security backport**, despite
  process.versions displaying Brotli1.1.0. Version-only matching can mislead.

The [Node security release](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)
also identifies high DNS/TLS issues CVE-2026-105482, CVE-2026-105483 and
CVE-2026-106069 relevant to the old n8n runtime but absent from the prior package
catalog. These are recorded separately, not concealed by the image count.
Current fixed backend URL inputs lack their untrusted/noncanonical-host
preconditions. Node26 fix line is **26.12.1**; WSL development Node24.22.0 should
move to **24.22.1** or a later compatible patch, while frontend22.23.4 is fixed.
See [Node22 release](https://github.com/nodejs/node/releases/tag/v22.23.4) and
[Node26 release](https://github.com/nodejs/node/releases/tag/v26.12.1).

### Fix decision and concrete maintenance boundary

No application dependency/OS/runtime upgrade was applied in this investigation.
Current runtime application versions are held and all protected services remain
unchanged. Blind transitive overrides, replacing Node inside n8n, or library-only
patching would not be adequately verified and could leave bundled code vulnerable.
Your constraint prohibits recreating/modifying original n8n resources.

Minimal next maintenance: qualify a vendor-supported n8n image with Node>=26.12.1,
patched native libraries and compatible app/database contracts in an isolated
copy; rerun all three workflows, credentials, publication and history/restore
checks. Review an exact image digest and rollback plan before approving normal
recreation with existing volumes/key. Do not overwrite a platform's managed
node_modules to chase the scanner. PostgreSQL candidate qualification is separate.
Keep services local and avoid untrusted downloads/workflows meanwhile.

The remaining pytest advisory is **Moderate upstream**, mitigated by random0700
test roots; no major-version test upgrade was introduced. npm application audit
remains zero in prior executed evidence. These package audits were not rerun
because no package/image changed.

### Complete critical/high catalog

### backend

| Advisory / scanner severity | Installed package | Scanner fixed version | Required input / assessment |
| --- | --- | --- | --- |
| [CVE-2026-85091](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/85xxx/CVE-2026-85091.json) / HIGH | deb/debian/zlib@1:1.3.dfsg+really1.3.1-1 | not fixed | Nonblocking zlib gzwrite stall followed by gzprintf/gzvprintf with stale buffer. **Range disagreement; no affected application call path found.** |

### n8n

| Advisory / scanner severity | Installed package | Scanner fixed version | Required input / assessment |
| --- | --- | --- | --- |
| [CVE-2026-82659](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/82xxx/CVE-2026-82659.json) / HIGH | npm/nodemailer@8.0.10 | 9.0.1 | Nodemailer message-level raw path/href bypasses file/URL access flags. **No customer-mail path found.** |
| [CVE-2026-13608](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/13xxx/CVE-2026-13608.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl LDAP SASL authentication with attacker-intercepted handshake. **No libcurl data path found in current workflows.** |
| [CVE-2026-54240](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/54xxx/CVE-2026-54240.json) / HIGH | apk/alpine/libde265@1.0.18-r0 | 1.1.1-r0 | Native libde265 decoding HEVC with oversized dimensions and 16-bit samples. **No HEVC decoder path in current workflows.** |
| [CVE-2026-54241](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/54xxx/CVE-2026-54241.json) / HIGH | apk/alpine/libde265@1.0.18-r0 | 1.1.1-r0 | Native libde265 SAO input allocation with crafted large HEVC dimensions. **No HEVC decoder path in current workflows.** |
| [CVE-2026-89161](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/89xxx/CVE-2026-89161.json) / HIGH | apk/alpine/pcre2@10.47-r1 | 10.48-r0 | Native PCRE2 JIT matching with previously copied subject passed as context. **No native attacker-regex path found.** |
| [CVE-2026-102276](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/102xxx/CVE-2026-102276.json) / HIGH | npm/brace-expansion@5.0.9 | 5.0.10 | Untrusted brace pattern with many comma groups or huge argument array. **Unused global npm tooling copy.** |
| [CVE-2026-102278](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/102xxx/CVE-2026-102278.json) / HIGH | npm/brace-expansion@5.0.9 | 5.0.11 | Untrusted deeply nested brace alternatives. **Unused global npm tooling copy.** |
| [CVE-2026-111759](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/111xxx/CVE-2026-111759.json) / HIGH | npm/markdown-it@13.0.2 | 14.3.2 | markdown-it typographer=true plus crafted unbalanced quote input. **No affected renderer setting/path found.** |
| [CVE-2026-111768](https://github.com/modelcontextprotocol/typescript-sdk/security/advisories/GHSA-46jr-4wx8-v453) / HIGH | npm/@modelcontextprotocol/sdk@1.31.0, npm/@modelcontextprotocol/server@2.0.0 | 2.3.0 | MCP is disabled; controller also checks enabled/auth middleware before SDK. **MCP disabled; no current entry point.** |
| [CVE-2026-114144](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/114xxx/CVE-2026-114144.json) / HIGH | npm/toml@3.0.0 | 5.0.1 | TOML unbounded integer conversion before range check. **No TOML parser path in current workflows.** |
| [CVE-2026-14456](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/14xxx/CVE-2026-14456.json) / HIGH | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL QUIC server with unbounded incoming Initial-packet channels. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-14457](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/14xxx/CVE-2026-14457.json) / HIGH | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL RFC7250 raw public keys with private key but no certificate and specific extension. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-18798](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/18xxx/CVE-2026-18798.json) / HIGH | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL QUIC server failing channel creation during Initial packet processing. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-19534](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/19xxx/CVE-2026-19534.json) / HIGH | npm/undici@6.28.0 | 6.28.1 | Affected undici WebSocket client receives unsolicited subprotocol in 101 reply. **Unused global npm tooling copy.** |
| [CVE-2026-54874](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/54xxx/CVE-2026-54874.json) / HIGH | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL DTLS endpoint buffering records for future epochs during handshake. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-63072](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/63xxx/CVE-2026-63072.json) / HIGH | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL CMS decrypt of attacker-controlled AES-WRAP-PAD message. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-63075](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/63xxx/CVE-2026-63075.json) / HIGH | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL QUIC peer sending ack-eliciting traffic without ACK of retained packets. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-63076](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/63xxx/CVE-2026-63076.json) / HIGH | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL CMP PBM verification with invalid protectionAlg ASN.1 type. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-77465](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/77xxx/CVE-2026-77465.json) / HIGH | npm/toml@3.0.0 | 4.2.0 | Deeply nested TOML arrays/inline tables. **No TOML parser path in current workflows.** |
| [CVE-2026-80229](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/80xxx/CVE-2026-80229.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl multi-interface pooled TLS connection surviving an OpenSSL provider context owner. **No libcurl data path found in current workflows.** |
| [CVE-2026-80230](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/80xxx/CVE-2026-80230.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl public-key pinning while both peer and hostname verification are disabled. **No libcurl data path found in current workflows.** |
| [CVE-2026-80231](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/80xxx/CVE-2026-80231.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl HTTPS connection reuse across different native CA store options. **No libcurl data path found in current workflows.** |
| [CVE-2026-80255](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/80xxx/CVE-2026-80255.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl cookie parsing of a tab before Secure, then a plaintext request. **No libcurl data path found in current workflows.** |
| [CVE-2026-82208](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/82xxx/CVE-2026-82208.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl wolfSSL cached trust store plus SSL_CTX callback replacement. **No libcurl data path found in current workflows.** |
| [GHSA-2x7j-588g-ccc2](https://api.github.com/advisories/GHSA-2x7j-588g-ccc2) / HIGH | npm/nodemailer@8.0.10 | 9.1.0 | Nodemailer parser receives very long comma-separated address list. **No customer-mail path found.** |
| [GHSA-v53p-9fqp-m79j](https://api.github.com/advisories/GHSA-v53p-9fqp-m79j) / HIGH | npm/nodemailer@8.0.10 | 10.0.6 | Nodemailer address fallback regex receives long whitespace-free nonaddress. **No customer-mail path found.** |
| [CVE-2026-103111](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/103xxx/CVE-2026-103111.json) / HIGH | apk/alpine/pcre2@10.47-r1 | 10.49-r0 | Attacker-controlled PCRE2 regex plus affected JIT API usage. **No native attacker-regex path found.** |
| [CVE-2026-111770](https://github.com/modelcontextprotocol/typescript-sdk/security/advisories/GHSA-jm63-cq47-j5jp) / HIGH | npm/@modelcontextprotocol/server@2.0.0 | 2.3.0 | MCP is disabled. **MCP disabled; affected sharing pattern not found.** |
| [CVE-2026-102826](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/102xxx/CVE-2026-102826.json) / HIGH | npm/simple-git@3.36.0 | 4.0.0 | Attacker-controlled simple-git clone include.path/includeIf config reaches Git. **No Git path in current workflows.** |
| [CVE-2026-102827](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/102xxx/CVE-2026-102827.json) / HIGH | npm/simple-git@3.36.0 | 4.0.0 | Attacker-controlled abbreviated dangerous simple-git push flags. **No Git path in current workflows.** |
| [CVE-2026-92392](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/92xxx/CVE-2026-92392.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.23.0-r0 | libcurl HTTP/2 upload receiving specific RST_STREAM errors. **No libcurl data path found in current workflows.** |
| [CVE-2026-102633](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/102xxx/CVE-2026-102633.json) / HIGH | apk/alpine/expat@2.8.3-r1 | 2.9.0-r0 | 32-bit libexpat allocator size overflow. **Architecture precondition absent.** |
| [CVE-2026-111755](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/111xxx/CVE-2026-111755.json) / HIGH | npm/follow-redirects@1.16.0 | 1.16.1 | Requires sensitive header name containing regex metacharacters plus cross-origin or downgrade redirect. **Library used; vulnerable header pattern absent in current flows.** |
| [CVE-2026-111756](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/111xxx/CVE-2026-111756.json) / HIGH | npm/follow-redirects@1.16.0 | 1.16.1 | Requires alternating-array header representation plus redirect. **Library used; vulnerable header container absent in current flows.** |
| [CVE-2026-63376](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/63xxx/CVE-2026-63376.json) / HIGH | npm/toml@3.0.0 | 4.1.2 | TOML table-path prototype traversal bypass. **No TOML parser path in current workflows.** |
| [CVE-2026-82209](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/82xxx/CVE-2026-82209.json) / HIGH | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl libpsl cookie Domain matching a public suffix. **No libcurl data path found in current workflows.** |
| [CVE-2026-86145](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/86xxx/CVE-2026-86145.json) / HIGH | apk/alpine/pcre2@10.47-r1 | 10.48-r0 | PCRE2 DFA recursive matching with small/cached workspace and missing size check. **No native attacker-regex path found.** |
| [CVE-2026-77214](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/77xxx/CVE-2026-77214.json) / HIGH | apk/alpine/expat@2.8.3-r1 | 2.9.0-r0 | Native XML_ParseBuffer caller advances length beyond allocated buffer. **No libexpat path found in current workflows.** |
| [CVE-2026-85091](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/85xxx/CVE-2026-85091.json) / HIGH | apk/alpine/zlib@1.3.2-r0 | 1.3.2-r1 | Nonblocking zlib gzwrite stall followed by gzprintf/gzvprintf with stale buffer. **Native library present; required write API not used by current flows.** |
| [CVE-2026-111767](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/111xxx/CVE-2026-111767.json) / HIGH | npm/@modelcontextprotocol/sdk@1.31.0 | 1.32.0 | mcp.access.enabled absent means false; anonymous /mcp-server/http is 404. **MCP disabled; no current entry point.** |
| [CVE-2026-114141](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/114xxx/CVE-2026-114141.json) / HIGH | npm/toml@3.0.0 | 5.0.1 | Many distinct TOML arrays-of-tables with repeated bookkeeping scans. **No TOML parser path in current workflows.** |
| [CVE-2026-114143](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/114xxx/CVE-2026-114143.json) / HIGH | npm/toml@3.0.0 | 5.0.1 | Very long dotted TOML key/header paths causing quadratic work. **No TOML parser path in current workflows.** |
| [CVE-2026-66046](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/66xxx/CVE-2026-66046.json) / HIGH | apk/alpine/expat@2.8.3-r1 | 2.8.4-r0 | libexpat parsing many nonnormalized XML attribute values. **No libexpat path found in current workflows.** |
| [CVE-2026-76641](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/76xxx/CVE-2026-76641.json) / HIGH | apk/alpine/expat@2.8.3-r1 | 2.8.4-r0 | libexpat external-entity parser struct mismatch and attribute handling. **No libexpat path found in current workflows.** |
| [CVE-2026-93748](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/93xxx/CVE-2026-93748.json) / HIGH | npm/http-cache-semantics@4.2.0 | not fixed | Shared HTTP response cache processes max-stale against security-zeroed entries. **Unused global npm tooling copy.** |
| [CVE-2026-93990](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/93xxx/CVE-2026-93990.json) / HIGH | apk/alpine/expat@2.8.3-r1 | 2.8.5-r0 | libexpat accepting malformed UTF-16 surrogate pairs. **No libexpat path found in current workflows.** |
| [CVE-2026-18924](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/18xxx/CVE-2026-18924.json) / CRITICAL | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl HTTP/2 push callback accepting push plus shared connections. **No libcurl data path found in current workflows.** |
| [CVE-2026-75803](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/75xxx/CVE-2026-75803.json) / CRITICAL | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | One-shot EVP_Cipher decrypt of empty ChaCha20-Poly1305/AES-OCB ciphertext. **Protocol/API precondition absent in current service configuration.** |
| [CVE-2026-102828](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/102xxx/CVE-2026-102828.json) / CRITICAL | npm/simple-git@3.36.0 | 4.0.1 | Attacker-controlled Git trailer command config reaches interpret-trailers. **No Git path in current workflows.** |
| [CVE-2026-102829](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/102xxx/CVE-2026-102829.json) / CRITICAL | npm/@simple-git/argv-parser@1.1.1 | 2.0.1 | Attacker VISUAL environment value passed to Git invoking editor. **No Git path in current workflows.** |
| [CVE-2026-106445](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/106xxx/CVE-2026-106445.json) / CRITICAL | npm/handlebars@4.7.9 | 4.7.10 | Requires attacker template plus prototype-method access and a reachable function. **No affected template path found.** |
| [CVE-2026-111497](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/111xxx/CVE-2026-111497.json) / CRITICAL | apk/alpine/brotli@1.2.0-r1 | 1.2.1-r0 | Installed APK Brotli 1.2.0-r1 and Node 26.7.0 bundled Brotli 1.2.0 predate fixes. **Affected native/runtime versions; untrusted response path remains possible.** |
| [CVE-2026-106446](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/106xxx/CVE-2026-106446.json) / CRITICAL | npm/handlebars@4.7.9 | 4.7.10 | Requires attacker-controlled AST object reaching Handlebars compilation. **No affected template path found.** |
| [CVE-2026-19931](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/19xxx/CVE-2026-19931.json) / CRITICAL | apk/alpine/curl@8.21.0-r0 | 8.22.0-r0 | libcurl Negotiate connection reuse after initially empty credentials. **No libcurl data path found in current workflows.** |
| [CVE-2026-63073](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/63xxx/CVE-2026-63073.json) / CRITICAL | apk/alpine/openssl@3.5.7-r1 | 3.5.8-r0 | OpenSSL CMP response validation of an unexpected sender distinguished name. **Protocol/API precondition absent in current service configuration.** |

### postgres

| Advisory / scanner severity | Installed package | Scanner fixed version | Required input / assessment |
| --- | --- | --- | --- |
| [CVE-2025-58187](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2025/58xxx/CVE-2025-58187.json) / HIGH | golang/stdlib@1.24.6 | 1.24.9 | Invokes affected Go APIs: crypto/x509 **No affected call path found (static).** |
| [CVE-2025-58188](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2025/58xxx/CVE-2025-58188.json) / HIGH | golang/stdlib@1.24.6 | 1.24.8 | Invokes affected Go APIs: crypto/x509 **No affected call path found (static).** |
| [CVE-2025-61723](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2025/61xxx/CVE-2025-61723.json) / HIGH | golang/stdlib@1.24.6 | 1.24.8 | Invokes affected Go APIs: encoding/pem **No affected call path found (static).** |
| [CVE-2025-61725](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2025/61xxx/CVE-2025-61725.json) / HIGH | golang/stdlib@1.24.6 | 1.24.8 | Invokes affected Go APIs: net/mail **No affected call path found (static).** |
| [CVE-2025-61726](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2025/61xxx/CVE-2025-61726.json) / HIGH | golang/stdlib@1.24.6 | 1.24.12 | Invokes affected Go APIs: net/url **No affected call path found (static).** |
| [CVE-2025-61729](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2025/61xxx/CVE-2025-61729.json) / HIGH | golang/stdlib@1.24.6 | 1.24.11 | Invokes affected Go APIs: crypto/x509 **No affected call path found (static).** |
| [CVE-2026-25679](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/25xxx/CVE-2026-25679.json) / HIGH | golang/stdlib@1.24.6 | 1.25.8 | Invokes affected Go APIs: net/url **No affected call path found (static).** |
| [CVE-2026-32280](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/32xxx/CVE-2026-32280.json) / HIGH | golang/stdlib@1.24.6 | 1.25.9 | Invokes affected Go APIs: crypto/x509 **No affected call path found (static).** |
| [CVE-2026-32281](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/32xxx/CVE-2026-32281.json) / HIGH | golang/stdlib@1.24.6 | 1.25.9 | Invokes affected Go APIs: crypto/x509 **No affected call path found (static).** |
| [CVE-2026-32283](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/32xxx/CVE-2026-32283.json) / HIGH | golang/stdlib@1.24.6 | 1.25.9 | Invokes affected Go APIs: crypto/tls **No affected call path found (static).** |
| [CVE-2026-33811](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/33xxx/CVE-2026-33811.json) / HIGH | golang/stdlib@1.24.6 | 1.25.10 | Invokes affected Go APIs: net **No affected call path found (static).** |
| [CVE-2026-33814](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/33xxx/CVE-2026-33814.json) / HIGH | golang/stdlib@1.24.6 | 1.25.10 | Invokes affected Go APIs: golang.org/x/net/http2, net/http **No affected call path found (static).** |
| [CVE-2026-33818](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/33xxx/CVE-2026-33818.json) / HIGH | golang/stdlib@1.24.6 | 1.25.13 | Invokes affected Go APIs: encoding/asn1 **No affected call path found (static).** |
| [CVE-2026-39820](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/39xxx/CVE-2026-39820.json) / HIGH | golang/stdlib@1.24.6 | 1.25.10 | Invokes affected Go APIs: net/mail **No affected call path found (static).** |
| [CVE-2026-39836](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/39xxx/CVE-2026-39836.json) / HIGH | golang/stdlib@1.24.6 | 1.25.10 | Invokes affected Go APIs: net **No affected call path found (static).** |
| [CVE-2026-42499](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/42xxx/CVE-2026-42499.json) / HIGH | golang/stdlib@1.24.6 | 1.25.10 | Invokes affected Go APIs: net/mail **No affected call path found (static).** |
| [CVE-2026-42504](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/42xxx/CVE-2026-42504.json) / HIGH | golang/stdlib@1.24.6 | 1.25.11 | Invokes affected Go APIs: mime **No affected call path found (static).** |
| [CVE-2026-56853](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/56xxx/CVE-2026-56853.json) / HIGH | golang/stdlib@1.24.6 | 1.25.13 | Invokes affected Go APIs: net/http **No affected call path found (static).** |
| [CVE-2026-56859](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/56xxx/CVE-2026-56859.json) / HIGH | golang/stdlib@1.24.6 | 1.25.13 | Invokes affected Go APIs: encoding/xml **No affected call path found (static).** |
| [CVE-2026-56862](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/56xxx/CVE-2026-56862.json) / HIGH | golang/stdlib@1.24.6 | 1.25.13 | Invokes affected Go APIs: crypto/tls **No affected call path found (static).** |
| [CVE-2026-56866](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/56xxx/CVE-2026-56866.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http, net/http/httputil **No affected call path found (static).** |
| [CVE-2026-78659](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/78xxx/CVE-2026-78659.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http, net/http/internal/http2, golang.org/x/net/http2 **No affected call path found (static).** |
| [CVE-2026-78660](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/78xxx/CVE-2026-78660.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http, net/http/internal/http2, golang.org/x/net/http2 **No affected call path found (static).** |
| [CVE-2026-78667](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/78xxx/CVE-2026-78667.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http **No affected call path found (static).** |
| [CVE-2026-78669](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/78xxx/CVE-2026-78669.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http, net/http/internal/http2, golang.org/x/net/http2 **No affected call path found (static).** |
| [CVE-2026-94439](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/94xxx/CVE-2026-94439.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http **No affected call path found (static).** |
| [CVE-2026-94440](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/94xxx/CVE-2026-94440.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/textproto, mime/multipart **No affected call path found (static).** |
| [CVE-2026-97031](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/97xxx/CVE-2026-97031.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: crypto/tls **No affected call path found (static).** |
| [CVE-2026-97032](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/97xxx/CVE-2026-97032.json) / HIGH | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http, net/http/internal/http2, golang.org/x/net/http2 **No affected call path found (static).** |
| [CVE-2026-39822](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/39xxx/CVE-2026-39822.json) / HIGH | golang/stdlib@1.24.6 | 1.25.12 | Invokes affected Go APIs: os **No affected call path found (static).** |
| [CVE-2026-86140](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/86xxx/CVE-2026-86140.json) / HIGH | apk/alpine/libxml2@2.13.9-r2 | not fixed | libxml2 xmlSnprintfElements XML/DTD validity error formatting. **Native SQL XML surface exists; no public application path found.** |
| [CVE-2026-85091](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/85xxx/CVE-2026-85091.json) / HIGH | apk/alpine/zlib@1.3.2-r0 | 1.3.2-r1 | Nonblocking zlib gzwrite stall followed by gzprintf/gzvprintf with stale buffer. **Native library present; required write API not used by current flows.** |
| [CVE-2026-78663](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/78xxx/CVE-2026-78663.json) / CRITICAL | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: net/http, net/http/internal/http2, golang.org/x/net/http2 **No affected call path found (static).** |
| [CVE-2026-39821](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/39xxx/CVE-2026-39821.json) / CRITICAL | golang/stdlib@1.24.6 | 1.25.13 | Invokes affected Go APIs: net/http, net/http/internal/http2, golang.org/x/net/idna **No affected call path found (static).** |
| [CVE-2026-56857](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/56xxx/CVE-2026-56857.json) / CRITICAL | golang/stdlib@1.24.6 | 1.26.9 | Invokes affected Go APIs: os, internal/syscall/windows **No affected call path found (static).** |
| [CVE-2025-68121](https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2025/68xxx/CVE-2025-68121.json) / CRITICAL | golang/stdlib@1.24.6 | 1.24.13 | Invokes affected Go APIs: crypto/tls **No affected call path found (static).** |

## 3. Unauthenticated ingress

Source/OpenAPI review and 17 nonmutating HTTP probes confirm:

| Entry point | Exposure / safeguards / residual risk |
| --- | --- |
| POST/GET /api/tickets; GET /{id}; GET /{id}/audit | No auth; original text readable locally. 64KiB actual body, field bounds, pagination, idempotency, sanitized validation, parameterized SQL, no-store. |
| POST /api/tickets/{id}/enrich; GET /enrichment | No auth; local caller may spend model resources/read advisory. Fixed model, one process slot, timeout/lease/attempt bounds. Missing ID returns404 without inference. |
| POST/GET /api/mock-crm/leads; GET /leads/{id} | No auth; local lead/contact reads and writes. Event/email registries, bounded fields, atomic audit/conflicts. |
| POST/GET /api/workflow-runs; GET /{execution_id} | No auth; metadata can be forged/read by local processes. Allowlisted metadata, bounded fields/pagination and unique identities are not source authentication. |
| GET /health, /ready, API schema/docs | Public sanitized status and schema metadata; no credential/error-trace response. |
| POST /api/reviewer/login | Public credential exchange with validation/throttle; does not grant decisions without valid credentials. |
| Next login page/assets/login/logout | Public UI/credential boundary; exact Origin/Fetch-Metadata guards for stateful proxies, HttpOnly Strict cookie, expiry and backend auth. Logout removes browser cookie only. |
| n8n POST /webhook/support-ticket-intake and /webhook/lead-intake | Unauthenticated; current stable webhook owners. Valid types/fields and backend constraints protect integrity, not sender identity. Prior hostile-Origin form was accepted; no extra forged record was needed to reconfirm source behavior. |
| n8n readiness and public login/settings metadata | No business authority. Workflow REST list401; MCP404/disabled. Scheduled digest has no public webhook and requires its existing encrypted service key. |

All host-published FlowForge ports are **127.0.0.1**:8001/3000/5679. PostgreSQL
has no published host port. FlowForge and personal n8n use distinct containers,
volumes and networks. Docker/OS administrators and trusted local processes can
still reach services; loopback is not an authentication scheme. CORS does not
prevent browser-form writes. No global intake quota/rate limit exists.

**Minimal trusted-local recommendation:** retain loopback and current validation/
resource bounds; use synthetic/non-sensitive data on the single-user host, do not
publish ports, and preserve opaque tracing IDs. Before accepting untrusted
senders/real multi-user data, qualify a scoped ingress header credential at n8n
and matching backend enforcement, with body/Origin/rate limits and tests. That
needs an authorized workflow/configuration change and synchronized published
export; it was not slipped into this parity-preserving investigation. An Origin
guard alone does not authenticate nonbrowser clients or forwarded n8n traffic.
No reverse proxy, Redis, paid service or new authentication platform is needed
for the current acceptance scope.

Residual ingress risk: **Medium** locally (forgery, disclosure, resource use).
Authenticated reviews/digest reads/generation still reject anonymous calls401.
AI remains advisory; an intake request cannot grant human approval.

## 4. Proposed checkpoint and tests

All original41 files were read/parsed or reviewed as code/diff and verified by
SHA256 unchanged before the documentation update. Classification:

- Backend boundary/database/test/runtime files:7.
- Frontend reader/proxy/test/runtime files:6.
- Verification/audit/recovery scripts:7.
- README/handover/runbook/security/implementation report:5.
- Intentionally generated redacted evaluation JSON:16.

No accidental, unrelated or temporary artifact was identified. The generated
JSON is acceptance evidence, not a dump, raw customer/model payload or secret.
Raw SARIF, private logs, decrypted values and encrypted backups stay outside Git.
No deletions/staging/commit were performed.

Fresh rechecks in this investigation:

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Full backend pytest | 233 | 0 | 0 |
| Frontend Vitest | 44 | 0 | 0 |
| API smoke | 8 | 0 | 0 |
| Nonmutating ingress/auth probes | 17 | 0 | 0 |

Published runtime/source parity passed again. Prior full acceptance/fault/
recovery/enrichment/restore suites remain the October23 evidence; **they were
not all rerun**. No runtime code/image changed, so frontend build/lint/types and
all failure drills were not repeated solely for documentation.

Preservation rechecked: all original business-row hashes match except the already
user-confirmed approval, which stays intact. Smoke adds only its synthetic ticket/
lead/audits. Original container identities/images/start/environment/mounts and
.env bytes are unchanged during this investigation. Personal n8n count remains37.
No normal DB restart/restore/migration, no original n8n changes, and no key,
credential or Ollama model changes. Whitespace/JSON/secret scan results are
recorded in the final investigation evidence.

## 5. Exact files changed by this investigation

1. README.md
2. docs/codex-handover.md
3. docs/implementation-09.md
4. docs/recovery-runbook.md
5. docs/security-review.md
6. docs/evaluation/implementation-09-acceptance.json
7. docs/implementation-09-exception-review.md (new)
8. docs/evaluation/implementation-09-exception-review.json (new)
9. docs/evaluation/implementation-09-vulnerability-triage.json (new)
10. docs/evaluation/implementation-09-secrets.json (refreshed redacted scan)

Total proposal is now **44 files**, all unstaged/uncommitted on
`implementation-09-testing-security`, HEAD973c408. The exact44-file manifest is
in implementation-09-acceptance.json; its initial41-file hash review is retained
in exception-review.json. Main/origin main remain29aa141. No push/merge/deletion.

## 6. Approved acceptance and remaining boundaries

**ACCEPT WITH DOCUMENTED EXCEPTIONS** for the existing trusted-local scope:

- History: exact missing rows identified, protected copies secured, current/
  published definitions and retained execution/credential rows intact. Automatic
  retention is strongly supported, but historical causation is not proven.
- Images: individual findings are triaged and retained. n8n runtime/native
  maintenance remains a **High** priority; no broad/exhaustive nonreachability
  or production safety claim.
- Ingress: **Medium** unauthenticated local surface is explicit; existing human
  decision controls and workflow contracts remain intact.
- pytest: upstream **Moderate**, local mitigation verified; session revocation/
  loopback HTTP: **Low** in this deployment.

Acceptance means acknowledging these residual risks, not approving public
deployment or suppressing findings. If every historical autosave must remain
inside the live database or all high/critical packages must be patched first,
choose HOLD and authorize a separate maintenance plan.

The user's final acceptance with documented exceptions is recorded on
2026-10-24 for trusted-local development only. The risks above remain open.
Implementation 09 remains unstaged/uncommitted: this acceptance explicitly
does not authorize a Git commit, push or merge. Preserve the investigation
reports and protected encrypted history archives; follow-ups require their own
reviewed scope and evidence.
