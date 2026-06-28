# Implementation Plan — docent-investigation-skill (front half, v1)

Source spec: `C:\PLATFORMS\PROJECTS\10X-Human-AI Interaction\VNEG_SPEC_docent-investigation-skill.md`
Pipeline: `/vneg-build`. This plan fills `plan_output_shape.md` and must pass `VNEG_PLAN_ACCEPTANCE_GATE.md`.

## 1. Mode
**Greenfield** — new standalone public repo `docent-investigation-skill` (owner `tarionai`), structured as a
Claude Code plugin marketplace mirroring `TransluceAI/claude-code-plugins`. Not the FirstLight monorepo,
not the upstream Transluce repo. Created on disk at `C:\PLATFORMS\PROJECTS\docent-investigation-skill`
(`git init`, branch `main`).

## 2. Current Repository Baseline
N/A — greenfield. No existing build/test/API surface. (Section required only for existing-repo work.)

## 3. Architecture Intake Summary
- **Product goal:** ship a Claude Code skill (`investigation`) that drives a complete, honest behavioral
  investigation on Docent — ingest real agent runs → author + evaluate a rubric for one failure mode via
  the Docent SDK → measure flag-frequency → anchor against a ground-truth oracle and report honestly
  (incl. nulls). Published as Ed's own installable marketplace plugin + a public Docent collection.
- **Target stack:** Python 3.11+ (Docent SDK `docent>=0.1.74`); Claude Code plugin/skill markdown; a small
  Python validation harness; `uv` for the docent MCP server launch. No web framework, no DB.
- **Target behavior (LOCKED at plan time): false-success declaration** — agent declares the task done/solved
  while the resolution oracle says tests fail. Chosen over *premature convergence* because Premise 3's
  trajectory-format finding makes false-success **directly oracle-checkable** (`report.json` resolved flag),
  giving the honesty anchor (N5) a clean cross-tab and a measurable rubric precision. Premature convergence
  → deferred to vNext (subjective; not in the oracle).
- **Modules/components:**
  1. *Marketplace/plugin scaffold* — `.claude-plugin/marketplace.json`, `plugins/docent-investigation/`
     with `.claude-plugin/plugin.json`, `.mcp.json`, `skills/investigation/SKILL.md` (+ skill reference files).
  2. *Local sanity harness* — `tools/plugin_sanity.py`, a parameterized reproduction of upstream
     `plugin-sanity.yml` validation logic (JSON validity, declared skill files exist + non-empty, `.mcp.json`
     `mcpServers.docent` shape, plugin/marketplace version match, forbidden-file check).
  3. *Trace transform* — `src/docent_investigation/transform.py`, a pure `.traj + report.json → AgentRun`
     converter (side-effect-free).
  4. *Docent client adapter* — `src/docent_investigation/docent_client.py`, a thin typed wrapper over the
     SDK calls (boundary module; only place that does network I/O).
  5. *Investigation skill guide* — `skills/investigation/SKILL.md` + reference files that walk Claude through
     the end-to-end procedure, calling (3) and (4).
  6. *Honesty anchor + report* — `src/docent_investigation/anchor.py` (oracle cross-tab → precision/recall)
     and `reports/`.
- **External interfaces (designed boundaries, fixable first):**
  - *Claude Code plugin/marketplace contract* — schema enforced by upstream `plugin-sanity.yml` (captured
    verbatim below). This is the one external wire contract; Node N0 builds to it.
  - *Docent SDK* (`docent>=0.1.74`): `create_collection`, `add_agent_runs`, `make_collection_public`,
    `create_rubric`, `start_rubric_eval_job`, `get_rubric_run_state` (validated 2026-06-27 — spec §Validation).
  - *docent MCP server*: `uv tool run --from docent-python>=0.1.74 docent-mcp` (mirrors upstream `.mcp.json`).
  - *SWE-bench/experiments* trace source: `evaluation/verified/<date>_<model>/{trajs/*.traj, logs/<id>/report.json}`.
- **Shared primitives (reference inventory — NOT a build order):** `AgentRun`, `Transcript`, `ChatMessage`
  (from `docent.data_models`), `Rubric` + `output_schema` (from `docent.judges.types`), an internal
  `OracleLabel`/`Verdict` result type, a `FlagRate`/`AnchorStats` result type.
- **Integration seams:** (a) transform→client (AgentRun handed to `add_agent_runs`); (b) client→Docent
  (network); (c) skill guide→both modules; (d) MCP server↔skill (Claude calls docent tools at runtime).
- **Ambiguities:** see §9.

## 4. Dependency Graph
- **Nodes:** N0 scaffold+sanity (boundary), N1 transform, N2 client adapter, N3 investigation skill guide,
  N4 batch+frequency, N5 honesty anchor, N6 report+publish+(coordinated PR).
- **Directed edges:** N0→N3 (skill lives in scaffold); N1→N2 (AgentRun feeds client); N1→N3, N2→N3 (skill
  calls both); N2→N4 (batch reuses client); N4→N5 (frequency feeds cross-tab); {N3,N4,N5}→N6.
- **Leaf nodes (no internal deps):** N0, N1.
- **Service nodes (pure logic, no I/O):** N1 transform, N5 anchor stats.
- **Integration nodes (cross a boundary / network):** N2 client adapter, N4 batch run, N6 publish/PR.
- **Terminal nodes:** N6.

## 5. Primitive Layer
- **Primitive types:** `AgentRun`, `Transcript`, `ChatMessage` (SDK, wrapped — never re-implemented);
  internal `TraceRecord` (one `.traj` + its oracle label, pre-conversion).
- **Enums:** `OracleLabel = {RESOLVED, UNRESOLVED}`; `Verdict = {FALSE_SUCCESS, NOT_FLAGGED, UNCERTAIN}`.
- **DTOs:** `RubricSpec` (rubric_text + output_schema); `FlagRate` (n, flagged, rate); `AnchorStats`
  (precision, recall, n, confusion-cells, null-flag).
- **Error/result types:** `IngestResult` (collection_id, run_ids, public_url); `EvalResult` (rubric_id,
  job_id, per-run labels).
- **Schemas:** rubric `output_schema` (JSON Schema: `{label: enum[false_success, not_flagged], explanation:
  cited}`); plugin manifest schemas (external, §6 N0).
- **Validators:** `tools/plugin_sanity.py`; transform input validator (well-formed `.traj`).
- **Files allowed for primitive work:** `src/docent_investigation/types.py` (created when its first consumer
  — N1 — needs it; NOT built ahead as a standalone layer).

## 6. Node Execution Queue
Ordered to deliver the §7 First Vertical Slice first. N0 is the single external boundary contract; N1→N2
are the slice's data path and live thread; N3 productizes the slice into the skill; N4–N6 scale + anchor +
publish.

### N0 — Marketplace/plugin scaffold + local sanity harness  *(FIRST EXECUTABLE — external boundary contract)*
- **Node ID:** N0
- **Purpose:** stand up the installable plugin-marketplace skeleton and a local check reproducing the
  upstream `plugin-sanity` validation, so structure is correct before any logic.
- **Depends on:** nothing.
- **Public contract:** repo root has `.claude-plugin/marketplace.json`; `plugins/docent-investigation/`
  has `.claude-plugin/plugin.json`, `.mcp.json`, `skills/investigation/SKILL.md` + declared reference files;
  `tools/plugin_sanity.py` exits 0. Installable via `/plugin marketplace add tarionai/docent-investigation-skill`.
- **Inputs:** the captured upstream contract (below).
- **Outputs:** valid manifests + passing sanity check.
- **Observable increment:** `python tools/plugin_sanity.py` exits 0 (a test stands in for the user); the
  marketplace is structurally installable. **No Docent access required.**
- **State:** none (static files).
- **Invariants:** all three JSON files parse; `plugin.json.name == "docent-investigation"`; version is semver;
  `marketplace.json` plugin entry version == `plugin.json` version; `.mcp.json.mcpServers.docent` has
  `type=="stdio"`, `command=="uv"`, `args` contains `"--from"`; every skill file the manifest declares exists
  and is non-empty; no `.mcp.local.json` / `docent.env*` present.
- **Required tests:** `tools/plugin_sanity.py` run as the test (asserts every invariant above); a deliberately
  broken-manifest fixture proves it fails closed.
- **Allowed files:** `.claude-plugin/marketplace.json`, `plugins/docent-investigation/**`, `tools/plugin_sanity.py`,
  `tests/test_plugin_sanity.py`, `README.md`, `.gitignore`, `pyproject.toml`.
- **Forbidden files:** `src/**` (no logic yet), any `.mcp.local.json`, any `docent.env*`, anything under the
  upstream Transluce repo.
- **Out of scope:** real skill prose (placeholder non-empty stubs only), any SDK calls.
- **Completion commands:** `python tools/plugin_sanity.py && python -m pytest tests/test_plugin_sanity.py -q`.
- **Readiness status:** READY (unblocked; build now).

### N1 — Trace transform (`.traj + report.json → AgentRun`)  *(first step of the vertical slice's data path)*
- **Node ID:** N1
- **Purpose:** convert one real SWE-bench trajectory + its oracle into a Docent `AgentRun` carrying per-step
  tool calls and the resolved/unresolved label in metadata.
- **Depends on:** N0 (repo exists). Logic-independent of N0.
- **Public contract:** `transform.traj_to_agent_run(traj_path, report_path) -> AgentRun` and
  `transform.load_oracle(report_path) -> OracleLabel`.
- **Inputs:** one `.traj` file, one `report.json`.
- **Outputs:** one `AgentRun(transcripts=[Transcript(messages=[ChatMessage(...tool_calls...)])],
  metadata={"scores": {"resolved": <bool>}, "instance_id": <str>, "model": <str>})`.
- **Observable increment:** a golden test converts a checked-in real fixture trajectory and asserts the
  AgentRun has ≥1 tool-call message and `metadata.scores.resolved` set. **No Docent access required.**
- **State:** none (pure function).
- **Invariants:** deterministic; no network/file writes/clock/randomness; round-trips per-step content;
  raises on malformed `.traj` rather than emitting a partial AgentRun.
- **Required tests:** golden test on one committed real fixture; malformed-input raises.
- **Allowed files:** `src/docent_investigation/transform.py`, `src/docent_investigation/types.py`,
  `tests/test_transform.py`, `tests/fixtures/<instance_id>.traj`, `tests/fixtures/<instance_id>.report.json`.
- **Forbidden files:** `docent_client.py`, any skill markdown, any network code.
- **Out of scope:** batching, network ingest.
- **Completion commands:** `python -m pytest tests/test_transform.py -q`.
- **Readiness status:** READY (unblocked once one real fixture is downloaded; download is read-only public data).

### N2 — Docent client adapter + live one-run thread  *(COMPLETES the First Vertical Slice)*
- **Node ID:** N2
- **Purpose:** thin typed wrapper over the SDK; then drive the end-to-end one-run thread:
  create collection → ingest 1 AgentRun → make public → create rubric → start eval → poll → 1 verdict.
- **Depends on:** N1 (AgentRun), N0 (repo).
- **Public contract:** `DocentClientAdapter` with `create_collection(name)`, `ingest(runs)`,
  `make_public(collection_id)`, `create_rubric(collection_id, spec)`, `evaluate(collection_id, rubric_id,
  max_agent_runs)`, `read_verdicts(collection_id, rubric_id) -> list[Verdict]`.
- **Inputs:** Docent API key/URL (Premise 2), one AgentRun from N1, a `RubricSpec`.
- **Outputs:** `IngestResult` (public_url) + one `Verdict`.
- **Observable increment:** running the thread on ONE real run prints a public collection URL + one rubric
  verdict (false_success / not_flagged). A mocked-client unit test stands in until live creds exist.
- **State:** remote collection (single-writer: this adapter is the only module that writes to Docent).
- **Invariants:** all network I/O confined to this module; wrapper methods are typed (no leaking SDK internals
  to callers); idempotent collection naming guard (don't silently create duplicates).
- **Required tests:** unit test against a mocked SDK client (no network); **live smoke test gated on Premise 2.**
- **Allowed files:** `src/docent_investigation/docent_client.py`, `scripts/one_run_thread.py`,
  `tests/test_docent_client.py`.
- **Forbidden files:** `transform.py` (read-only import), skill markdown, batching code.
- **Out of scope:** batch of >1 run, frequency stats, honesty anchor.
- **Completion commands:** `python -m pytest tests/test_docent_client.py -q` (always); `python
  scripts/one_run_thread.py --one` (live — **only after Premise 2 resolved**).
- **Readiness status:** PARTIAL — wrapper + mocked test READY now; live thread BLOCKED on Premise 2.

### N3 — `investigation` skill guide
- **Node ID:** N3
- **Purpose:** author the SKILL.md (+ reference files) that walks Claude through the full procedure using N1/N2.
- **Depends on:** N0 (scaffold), N1, N2 (the procedure it documents).
- **Public contract:** `skills/investigation/SKILL.md` frontmatter (`name: investigation`, `description`,
  `alwaysApply: false`) + reference files; replaces N0's placeholder stubs.
- **Inputs:** the working transform + adapter.
- **Outputs:** a skill that, when invoked, reproduces the one-run slice and (later) the batch.
- **Observable increment:** invoking the skill in Claude Code drives ingest→rubric→verdict (manually
  demonstrable; the slice now runs from the user's seat, not just a script).
- **State:** none.
- **Invariants:** guide references only real, validated SDK method names; no instruction depends on an
  unvalidated capability; sanity harness still passes (skill files non-empty, declared set complete).
- **Required tests:** `python tools/plugin_sanity.py` (skill-file completeness); prose review against §Validation.
- **Allowed files:** `plugins/docent-investigation/skills/investigation/**`.
- **Forbidden files:** `src/**` (no logic changes from prose work).
- **Out of scope:** the back-half research items (spec §DEFERRED).
- **Completion commands:** `python tools/plugin_sanity.py`.
- **Readiness status:** READY to author prose now (procedure is validated); live demonstration BLOCKED on Premise 2.

### N4 — Batch the bounded sample; compute flag-frequency
- **Node ID:** N4
- **Purpose:** ingest 200–500 runs from one Verified submission; evaluate the rubric over the batch; compute
  flag-rate.
- **Depends on:** N2 (adapter), N1 (transform).
- **Public contract:** `scripts/run_investigation.py --collection <name> --submission <path> --n <N>` →
  `FlagRate`.
- **Inputs:** a downloaded Verified submission (Premise 3), Docent creds (Premise 2).
- **Outputs:** `FlagRate` (n, flagged, rate) + public collection URL.
- **Observable increment:** a printed flag-frequency over N real runs + the public collection URL.
- **State:** the batch collection (single-writer: adapter).
- **Invariants:** N reported honestly (no silent truncation/sampling without logging); reuses N2 adapter
  (no second writer).
- **Required tests:** dry-run on a 3-run fixture with mocked client; live batch gated on Premise 2.
- **Allowed files:** `scripts/run_investigation.py`, `src/docent_investigation/batch.py`, `tests/test_batch.py`.
- **Forbidden files:** `docent_client.py` (read-only import).
- **Out of scope:** precision/recall (N5).
- **Completion commands:** `python -m pytest tests/test_batch.py -q`; live batch after Premise 2.
- **Readiness status:** BLOCKED on Premise 2 (live) + Premise 3 (submission chosen); code+mock READY.

### N5 — Honesty anchor (oracle cross-tab → precision/recall; pre-registered)
- **Node ID:** N5
- **Purpose:** cross-tab rubric flags against the resolved/unresolved oracle; compute precision/recall;
  report nulls if no separation. Pre-register thresholds BEFORE looking at results.
- **Depends on:** N4 (flags + per-run oracle labels).
- **Public contract:** `anchor.compute(verdicts, oracle_labels) -> AnchorStats`; a committed
  `PRE_REGISTRATION.md` written before N4 runs live.
- **Inputs:** per-run verdicts + oracle labels.
- **Outputs:** `AnchorStats` (precision, recall, confusion cells, null-flag).
- **Observable increment:** a precision/recall table + an explicit null verdict if the rubric doesn't separate.
- **State:** none (pure stats).
- **Invariants:** pure function (no I/O); thresholds read from the pre-registration file, not chosen post-hoc;
  reports nulls honestly.
- **Required tests:** unit test on a synthetic confusion matrix (no network); pre-registration file exists
  and predates the live run (git timestamp).
- **Allowed files:** `src/docent_investigation/anchor.py`, `tests/test_anchor.py`, `PRE_REGISTRATION.md`.
- **Forbidden files:** network code, batch code.
- **Out of scope:** scaled human labeling / IRR (deferred).
- **Completion commands:** `python -m pytest tests/test_anchor.py -q`.
- **Readiness status:** code + pre-registration READY now; numbers BLOCKED on N4 (→ Premise 2).

### N6 — Report + publish + (Slack-gated) upstream PR
- **Node ID:** N6
- **Purpose:** 1–2 page report; publish the public collection URL; ship Ed's standalone marketplace;
  if Slack-approved, open the coordinated upstream PR (add `skills/docent/investigation.md` + TOC line).
- **Depends on:** N3, N4, N5.
- **Public contract:** `reports/INVESTIGATION_REPORT.md` + public collection URL + pushed public repo.
- **Inputs:** all prior outputs.
- **Outputs:** citable artifact set.
- **Observable increment:** a public repo + public Docent collection URL a third party can open and re-run.
- **State:** published artifacts.
- **Invariants:** report states the known blind spot (spec §Known blind spot) and any nulls; upstream PR
  opened ONLY after Slack go (coordinate-first).
- **Required tests:** cold-clone reproduce check (`git clone` → `plugin_sanity` passes → one-run thread runs).
- **Allowed files:** `reports/**`, `README.md`.
- **Forbidden files:** opening the upstream PR before Slack approval.
- **Out of scope:** spec §DEFERRED back-half.
- **Completion commands:** cold-clone reproduce; `python tools/plugin_sanity.py`.
- **Readiness status:** BLOCKED on N4/N5 (→ Premise 2) and (for the coordinated PR) on Slack go.

## 7. First Vertical Slice
- **User action:** a developer installs Ed's plugin (`/plugin marketplace add tarionai/docent-investigation-skill`)
  and invokes the `investigation` skill on one SWE-bench trajectory.
- **Entry boundary:** the `investigation` skill (N3) → `scripts/one_run_thread.py` (N2).
- **Modules touched:** transform (N1) → docent_client adapter (N2), inside the scaffold (N0); skill guide (N3).
- **Output:** one ingested run in a **public** Docent collection (URL) + one rubric verdict
  (false_success / not_flagged).
- **Tests proving the slice works:** N1 golden transform test; N2 mocked-client unit test (always-green);
  N2 live one-run smoke (`scripts/one_run_thread.py --one`) once Premise 2 is resolved — prints the public
  URL + verdict.

## 8. Gates
- **Hard gates:** `python tools/plugin_sanity.py` exits 0; `pytest` green for every non-live test; transform
  is pure (no I/O); all network confined to `docent_client.py`.
- **Soft gates:** skill prose references only validated SDK methods; report includes the blind-spot caveat.
- **Regression checks:** sanity harness re-run after every node that touches plugin files; full `pytest` per node.
- **Scope checks:** no back-half (spec §DEFERRED) work; no upstream-repo edits in v1; no second Docent writer.
- **Verification record path:** `docs/verification/` — one record per completed node (commands run + outcomes).

## 9. Blockers / Assumptions / Local Details
- **BLOCKER — Premise 2 (external Docent access).** Live N2 thread, N4 batch, N5 numbers, N6 publish all
  require a hosted transluce.org account (external create-collection + rubric-eval + `make_collection_public`)
  OR self-host (`docker-compose` + Ed's LLM key). Resolution is an operator action; not buildable in-session.
  N0, N1, N2-wrapper+mock, N3-prose, N5-code proceed without it.
- **ASSUMPTION — chosen Verified submission has structured `.traj`.** Premise 3 is PASS in general, but the
  specific submission (SWE-agent/OpenHands lineage) whose trajectories carry per-step tool calls must be
  picked + spot-checked at N1. If none qualify → fallback: generate traces (spec Premise 3 fallback, +~1wk).
- **ASSUMPTION — MCP launch string.** `.mcp.json` mirrors upstream `uv tool run --from docent-python>=0.1.74
  docent-mcp`; verify the server starts at N0. (`docent-python` redirects to `docent`.)
- **ASSUMPTION — judge LLM cost borne by Ed's own LLM key** configured in the SDK/MCP env (SDK bundles
  Anthropic/OpenAI/Google). Verify when Premise 2 is stood up.
- **LOCAL DETAIL — names:** repo `docent-investigation-skill`, owner `tarionai`, plugin `docent-investigation`,
  skill `investigation`. Adjustable without changing the plan.
- **LOCAL DETAIL — skill-file set:** Ed's `investigation` skill declares its own reference files (e.g.
  `SKILL.md`, `rubric-reference.md`, `oracle-anchor.md`); the local sanity harness validates against Ed's
  declared set, NOT Transluce's fixed 7-file `docent` set.
- **LOCAL DETAIL — pin `docent` vs `docent-python`** in `.mcp.json`: default to the upstream-proven
  `docent-python>=0.1.74`; may switch to canonical `docent>=0.1.74` if the MCP entry point matches.

## 10. First Executable Node
- **Node ID:** N0 — marketplace/plugin scaffold + local sanity harness.
- **Why this node is first:** it is the single **external wire/boundary contract** (the Claude Code
  plugin-marketplace schema enforced by upstream `plugin-sanity.yml`). Per the VNEG gate, one external
  boundary contract may come first. It is unblocked by all three premises, so it delivers real, verifiable
  progress immediately while Premise 2 is resolved out-of-band.
- **Observable increment it delivers:** `python tools/plugin_sanity.py` exits 0 and the marketplace is
  structurally installable (`/plugin marketplace add ...`) — a test stands in for the user.
- **Exact implementation prompt to use next:** see `docs/plans/NODE_N0_PROMPT.md` (bounded prompt; built
  alongside this plan).

---

### Captured external contract (from `TransluceAI/claude-code-plugins`, read 2026-06-27)
- **`plugin-sanity.yml` asserts:** `.claude-plugin/marketplace.json`, `<plugin>/.claude-plugin/plugin.json`,
  `<plugin>/.mcp.json` are valid JSON; required skill files exist + are non-empty; `.mcp.json.mcpServers.docent`
  is a dict with `type=="stdio"`, `command=="uv"`, `args` containing `"--from"`; `plugin.json.name`,
  semver `version`, marketplace version == plugin version; forbidden: `.mcp.local.json`, `docent.env`,
  `docent.env.*`.
- **`.mcp.json` (verbatim upstream):** `{"mcpServers":{"docent":{"type":"stdio","command":"uv","args":
  ["tool","run","--from","docent-python>=0.1.74","docent-mcp"]}}}`
- **`marketplace.json` shape:** `{name, owner, metadata:{description}, plugins:[{name, source, description,
  version, author, tags}]}`.
- **`plugin.json` shape:** `{name, version, description}`.
- **`SKILL.md` frontmatter:** `name`, `description`, `alwaysApply`.
