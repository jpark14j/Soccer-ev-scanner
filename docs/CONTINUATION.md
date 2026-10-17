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

## Next work (continue automatically)

1. Phase 8: extend actual immutable forward recording and exact-result labeling;
   prevent book/opposite duplicates and hindsight; implement cluster-aware
   scorecards, protocol locks, precision/power planning and reviewed suspension.
2. Add a disabled optional private off-host snapshot adapter and restore checks,
   with explicit ephemeral-storage, shared-budget and scheduler limitations.
3. Phase 9: reliability/performance/dashboard integration, full workflow tests,
   startup/security checks, comprehensive readiness report, commits and Draft PR
   #1/CI verification.

Blockers: no untouched outcomes or independent accuracy gain, no actual joint
ticket adapter, no configured durable remote service, no current NBA/MLB input
pipeline. Calendar-time evidence and user-configured storage cannot be invented.
