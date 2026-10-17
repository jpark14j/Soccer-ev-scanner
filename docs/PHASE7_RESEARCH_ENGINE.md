# Phase 7 — risk and dependent-combination research

Continues Phase 6 on the existing development branch. All frozen models,
approval gates and API budgets are preserved. No actual provider requests or
paid AI calls were made. The prior 485 tests passed before changes.

## Three distinct rankings

The original research grouping/evidence engine remains the gatekeeper. Equivalent
quotes are reconciled and opposing binary outcomes remain in details. Supported
experimental selections now additionally receive `risk-research-1` rankings:

- **MOST LIKELY TO WIN:** marginal model probability, with existing evidence
  tie-breaks. It is not a price/value ranking.
- **BEST RISK-ADJUSTED RESEARCH OPPORTUNITY:** only candidates whose entire
  nonzero supplied calibration range exceeds the current observed break-even.
  Score = `(lower range endpoint − 1/decimal odds) / (upper − lower)`. Higher is
  preferred, followed by narrower range, calibration/test sample support, lower
  estimated loss probability and existing evidence/freshness tie-breaks.
- **BEST SUPPORTED RESEARCH PARLAY:** existing weakest-leg evidence ranking for
  same-book 2/3-leg combinations, with dependency information. This is not a
  ranking of calibrated joint success or expected returns.

The default single uses the price-sensitivity ranking when supported; otherwise
it explicitly falls back to the probability ranking. The previous evidence-first
selection remains available to existing callers. A high-probability selection
can have an unfavorable price. No numerical EV, Kelly stake, profitability,
Sharpe ratio or calibrated event-specific confidence bound is generated. The
loss probability is the model's `1 − p`, not an independent risk estimate.

The ranges are historical calibration-bucket intervals. They need not cover
the unknown probability for this game. Consequently this score is a transparent
**research sensitivity measure**, not proven risk-adjusted value. Missing live
model disagreement is explicitly unavailable, not zero. Source proof, sample
support, historical evidence and missing team inputs remain separate diagnostics.
Singles are not automatically compared with or displaced by parlays.

## Dependent combinations and settlement research

The existing bounded generator now retains separate shortlists for same-game,
multi-game and mixed 2/3-leg research. Shared outcomes, contradictions and nested
selections remain rejected. The default top parlay retains its different-game
restriction; linked formats appear separately as research with missing joint
evidence. Every combination still uses one observed sportsbook, and theoretical
products never become executable tickets.

The reusable joint-research interface enumerates an explicitly supplied coherent
soccer score scenario for linked games, preserving win/push/half-win/half-loss/
loss states. It does not splice individually calibrated marginals into a score
grid. No current coherent joint forecast is silently substituted for the frozen
binary models. Without that evidence the compatible SGP remains unpriced joint
research. Across games, only conditional Frechet logical all-full-win bounds can
be shown when each component exists; **no independence/product estimate is
used**. Mixed formats keep their same-game component dependencies. Logical bounds
and deterministic scenarios are not calibrated forecasts or ticket settlements.

The new offline `joint_validation.py` report replays the existing fitted goal
parameters, with no new fitting or parameter tuning. It compares the three Phase
6 settlement tasks with a simpler coherent training-only league-Poisson score
baseline on identical 342 EPL / 210 Bundesliga / 272 Ligue 1 test matches. Both
models enumerate dependent selections inside the same score distribution.

All-full-win Brier/log loss, ECE, calibration bins, proper multiclass settlement
scores, paired day-block score intervals and descriptive quarter stability are
stored. Prespecified ±10% goal-rate perturbations, zero-rho and temperature-one
scenarios expose sensitivity. Their ranges are **not confidence intervals**.
For BTTS Yes + Over 2.25, median scenario probability range widths are 10.70,
12.24 and 11.65 percentage points in EPL, Bundesliga and Ligue 1. Every new paired
binary Brier interval versus the league baseline includes zero. No reliable
joint advantage, approved joint model, actual ticket price or parlay EV follows.

Reproduce without network access:

```bash
OPENBLAS_NUM_THREADS=1 python -m intelligence.joint_validation --source work/phase2/source
```

The [report](../research_assets/quantitative/joint_validation.json) records the
source/code/parent-report hashes. Existing Phase 5/6 artifacts remain unchanged.
The dates were already examined by the project: these diagnostics are not fresh
independent confirmation or evidence of improved current prediction accuracy.

## Model accuracy and expansion audit

No additional challenger is tuned against the reused 2024–25 test period. The
previous Poisson/Dixon-Coles/beta/annual-refit comparisons provide no credible
independent replacement evidence. A predeclared forward policy is now frozen for
the next milestone; actual future games must provide the next independent test.

Current inference remains experimental EPL BTTS/exactly-2.5 goals, Bundesliga BTTS
and Ligue 1 exactly-2.5 goals, conditional on existing complete fresh reconciled
results, supported contracts, current Ontario prices and calibration gates.
La Liga and Serie A required 2024–25 archives remain 370/380; no model transfer or
new fit is justified. NBA/MLB archives do not supply current team/player/context
inputs or current market validation. Permitted current results, NBA minutes and
availability, MLB pitchers/lineups/park context and sport-specific independent
validation are still needed. Player-prop probabilities are not manufactured.

The four pages, local assistant and approved-opportunity decision remain intact.
New summaries and format details are on AI Dashboard and Best Picks & Parlays.
Offline joint comparisons are expandable under Model & Data Diagnostics.
