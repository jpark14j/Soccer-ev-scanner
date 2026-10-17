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

## Next work (continue automatically)

Phase 9: finish concise reliability/dashboard integration, enforce request-free
ordinary rendering, full workflow tests, isolated startup/security checks,
comprehensive readiness report, final development commit and Draft PR #1/CI.
Keep all four pages and existing tools. No actual provider requests are needed.

Blockers: no untouched outcomes or independent accuracy gain, no actual joint
ticket adapter, no configured durable remote service, no current NBA/MLB input
pipeline. Calendar-time evidence and user-configured storage cannot be invented.
