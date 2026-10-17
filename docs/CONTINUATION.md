# Coordinated phases 7–9 checkpoint

Starting verified commit: `26ec3869f4aeddccce49a42d21176c43c5430fc5`.
Branch: `development/verified-sports-intelligence`; use Draft PR #1 only.
Main/production/paid settings and request caps must stay unchanged.

## Milestone 7

Implemented the defined research sensitivity/probability fallback ranking,
compatible per-format parlay shortlists, explicit no-independence joint research
and offline baseline/sensitivity/quarter diagnostics. Existing models were not
replaced, approved or tuned again. Prior clean branch work was preserved.

Files: `intelligence/risk_research.py`, `joint_research.py`, `joint_validation.py`,
`research_top.py`, `parlay_intelligence.py`, `top_research_ui.py`, `quant_ui.py`;
`config/forward_research_policy.json`; `research_assets/quantitative/joint_validation.json`;
`tests/test_master_risk_joint.py`; this checkpoint and `docs/PHASE7_RESEARCH_ENGINE.md`.

Validation: 485 baseline tests, 36 targeted old/new tests and all 498 milestone
tests passed. Compilation/whitespace checks pass. CI is checked after publication.
No actual provider requests were made. Inspect `git log -1` for the checkpoint
commit SHA; the starting verified SHA above is the parent baseline, not a claim
that a document can contain its own future commit hash.

## Milestone 8

Phase 7 commit: `9512af153610f3a0affbfd8342a040128062a2a6`.
Its GitHub Actions run `39000501566` passed. All 528 tests pass after Phase 8;
compilation, dependency consistency and whitespace checks pass. The Phase 8
commit follows this verified parent; inspect `git log -1` for the current SHA.

Implemented immutable protocol-locked deduplicated forward records, exact cached
result reconciliation, quarantine/research holds, calibration/block scorecards,
precision/power plans, league-scoped reviewed suspension, and disabled private
Supabase snapshots with checksum readback/new-file restore. Restored provider
allowances remain held across UTC resets until explicit usage review. Online
workers remain disabled without supported shared transactional budgets/scheduler.

New files: `intelligence/forward_testing.py`, `forward_ui.py`,
`model_reliability.py`, `remote_backup.py`, `request_guard.py`;
`tests/test_forward_evaluation.py`, `tests/test_remote_backup.py`;
`docs/PHASE8_FORWARD_DURABILITY.md`.
Modified integration: analyst_config, cached_research, chat_privacy, cli,
current_results, lifecycle, odds_diagnostics, operations_ui, performance_ui,
persistence, pipeline, processing, quota, research_top, storage, worker and
workspace_ui. Frozen models and approval policies are unchanged.

## Milestone 9 — locally verified final increment

Phase 8 commit: `96e97dafccbc6da555ef75e306b5b3c09bde0f76`.
Its GitHub Actions run `39001351737` passed 527 tests with one documented
private-archive skip. Phase 7 passed 497 with the same skip.

All 534 local tests now pass (49 added since Phase 6). Compilation, dependency,
whitespace, configured-secret and 34 protected-file checks pass. Isolated
Streamlit port 8515 returned HTTP 200 `ok` with credentials removed and requests
disabled. Actual provider requests and genuine new forward records remain zero.

Phase 9 adds provider-request-free startup/filtering, explicit capped refresh,
store-generation cache binding, five daily summaries, forward-aware local chat,
completed-and-fully-labeled cohort review, expiring registry safeguards and full
synthetic workflow tests. Files include app.py; analyst_context, cli, lifecycle,
llm, market_ui, model_reliability, pipeline, remote_backup, slate, top_research_ui,
quant_ui, research_views and workspace_ui; tests/test_master_workflow.py and the
stronger forward regression; README, verification, readiness and evidence docs.

Publication checkpoint: the final tested increment is complete locally. If the
branch still points at the Phase 8 SHA above, publish this verified tree without
resetting or rebuilding. If a later commit contains this checkpoint, inspect
`git log -1`, Draft PR #1 head and its CI result for the exact final SHA/status.
The document cannot contain its own future commit hash; final PR metadata records
it after publication. Keep PR #1 in draft, main and production unchanged.

No additional phase prompt is required. Remaining work is actual future evidence
and optional user setup: do not manufacture results, claim approval, activate
paid services or infer off-host durability from the tested fake transport.
Use docs/PHASES7_9_READINESS.md for the complete report and exact preview checks.

Blockers: no untouched outcomes or independent accuracy gain, no actual joint
ticket adapter, no configured durable remote service, no current NBA/MLB input
pipeline. Calendar-time evidence and user-configured storage cannot be invented.
