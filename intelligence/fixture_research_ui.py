"""Small quote-free research view; no provider requests or training on page load."""
from pathlib import Path
import json, sqlite3
import streamlit as st
from intelligence.domain import digest
from intelligence.data_adapters import ROOT
from intelligence.fixture_research import collect, combinations_for

REPORT = ROOT/'research_assets/team_sport_challengers.json'


def historical_evidence():
    try:
        report = json.loads(REPORT.read_text()); checksum = report.pop('sha256')
        if digest(report) != checksum:
            return {}
        code = digest(Path(__file__).with_name('team_rating.py').read_text())
        if any(r['code_sha256'] != code or r['approved'] or r['replaces_incumbent'] for r in report['reports'].values()):
            return {}
        return report['reports']
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def render(w, safe):
    try:
        result = collect(w.store, hours=w.settings.window_hours, leagues=w.leagues)
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError):
        st.caption('Fixture-only research unavailable: saved input validation failed. No probabilities were filled in.')
        return
    rows = result['forecasts']
    st.subheader('Model research without live odds')
    st.caption('Uses saved verified fixtures and results only. No API credits, paid AI or sportsbook prices are needed for this section.')
    if not rows:
        st.info('No current fixture-only forecast passes the input checks. The model studies below are historical evidence, not current picks.')
    for r in rows[:3]:
        with st.container(border=True):
            st.text(safe(r['event']+' · '+r['league']))
            from intelligence.consumer_ui import friendly_time
            st.caption(friendly_time(r['kickoff']))
            st.write(safe(('Both teams to score · ' if r['market']=='btts' else 'Total goals 2.5 · ')+r['selection']))
            st.write(f"Model estimate **{r['probability']:.1%}** · historical calibration range {r['lower']:.1%}–{r['upper']:.1%}")
            st.caption(f"Model-implied fair decimal {r['fair_odds']:.2f}; not an available sportsbook price. Experimental, unapproved; EV unavailable.")
            with st.expander('Statistics and missing evidence'):
                st.caption(safe(f"Model {r['model_version']} · {r['history_n']} earlier games · calibration {r['calibration_n']} · test {r['test_n']} · bucket {r['calibration_bin_n']}"))
                st.caption(safe('Results through '+r['training_end']+' · source checked '+r['source_observed_at']))
                for limitation in r['limitations']: st.text(safe(limitation))
                st.caption(result['note'])
    if rows:
        with st.expander('Unpriced 2-leg and 3-leg fixture research'):
            for size in (2, 3):
                candidates = combinations_for(rows, size, limit=1)
                if not candidates:
                    st.caption(f'No compatible {size}-leg fixture candidate; no selection is forced.')
                for c in candidates:
                    st.write(f'**{size}-leg research combination · no sportsbook ticket**')
                    for r in c['legs']: st.text(safe(f"{r['event']} · {r['selection']} · model {r['probability']:.1%}"))
                    lo, hi = c['logical_probability_bounds']
                    st.caption(f'Logical joint range {lo:.1%}–{hi:.1%}, conditional on the individual estimates. No calibrated parlay winning probability is available.')
                    st.caption('Fair-odds range and probability bounds are mathematical implications, not a quoted ticket or a confidence interval. No EV is calculated.')
                    for text in c['limitations']: st.text(safe(text))
    with st.expander('Soccer, NBA and MLB evidence and current-data blockers'):
        for league, problem in result['blockers'].items(): st.text(safe(league+': '+problem))
        from intelligence.epl_forecasts import load_artifact
        artifact = load_artifact()
        if artifact:
            task = artifact['tasks']['btts']; model = task['periods']['held_out']['model']
            st.text(f"Soccer · EPL BTTS frozen study · {model['n']} held-out games · Brier {model['binary_brier']['value']:.4f} · log loss {model['log_loss']['value']:.4f}. Research only.")
        for sport, r in historical_evidence().items():
            st.text(safe(f"{sport} · history through {r['data_end']} · {r['test_n']} chronological test games · challenger Brier {r['metrics']['binary_brier']['value']:.4f} · log loss {r['metrics']['log_loss']['value']:.4f}"))
            if r['incumbent_metrics']:
                interval = r['paired_minus_incumbent']['binary_brier']['interval']
                st.caption(f"Existing model Brier on {r['paired_test_n']} common test games: {r['incumbent_metrics']['binary_brier']['value']:.4f}. Paired difference interval {interval[0]:+.4f} to {interval[1]:+.4f}.")
            st.caption('No model replaced or approved. Historical testing does not make this old archive suitable for current games.')
        st.caption('NBA and MLB still need current licensed results and reconciled fixtures. Prices are never converted into model forecasts. Player props and live models require additional verified inputs.')
