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


def render(w, safe, sizes=(2,3)):
    try:
        result = collect(w.store, hours=168, leagues=w.leagues)
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError):
        st.caption('Fixture-only research unavailable: saved input validation failed. No probabilities were filled in.')
        return
    from intelligence.prediction_accuracy import saved_for_display
    rows = saved_for_display(w.store,result['forecasts'])
    st.subheader('Model research without live odds')
    st.caption('Uses saved verified fixtures and results only. No API credits, paid AI or sportsbook prices are needed for this section.')
    st.caption('Looks ahead seven days. Estimates can change as new games finish; expired inputs remove forecasts.')
    if not rows:
        st.info('No current saved prediction passes the recording and input checks. The next scheduled update may provide fresh research; historical studies are not current picks.')
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
                st.caption('Recorded before kickoff · '+friendly_time(r['recorded_at']))
                st.caption(result['note'])
    if 'Bundesliga' in w.leagues:render_score_research(w.store,safe,sizes)
    if rows:
        with st.expander('Unpriced 2-leg and 3-leg fixture research'):
            for size in sizes:
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
        from intelligence.recent_nba import load_report
        r=load_report()
        if r:
            st.text(f"Recent NBA regular-season study · {r['history_n']} games through {r['data_end']} · {r['test_n']} test games from 2025–26 · Brier {r['metrics']['binary_brier']['value']:.4f} versus simple baseline {r['baseline']['binary_brier']['value']:.4f} · log loss {r['metrics']['log_loss']['value']:.4f} · calibration error {r['ece']:.1%}.")
            st.caption('NBA archive updated; current fixture reconciliation and offseason roster readiness remain blocked. No model was approved or substituted for the existing model.')
            st.caption(f"Existing model on the same {r['paired_test_n']} test games: Brier {r['incumbent_metrics']['binary_brier']['value']:.4f}. The paired improvement interval includes zero; there is no credible replacement decision.")
            st.caption(r['attribution'])
        from intelligence.recent_mlb import load_report as mlb_report
        m=mlb_report()
        if m:
            st.text(f"MLB full-season 2025 study · {m['test_n']} held-out games · Brier {m['metrics']['binary_brier']['value']:.4f} · log loss {m['metrics']['log_loss']['value']:.4f} · calibration error {m['ece']:.1%}.")
            st.caption('This remains a historical study. The 2025 source cannot supply current 2026 game probabilities.')
            st.caption(m['source']['attribution'])
        st.caption('MLB still needs permitted 2026 results and fixtures. Prices are never converted into model forecasts. Player props and live models require additional verified inputs.')
        from intelligence.team_score_study import load_report as score_report
        study=score_report()
        if study:
            for sport,report in study['reports'].items():
                st.text(f"{sport} score challenger · {report['selected_variant']} · {report['partitions']['test']['n']} test games. Retrospective diagnostic; no model promoted.")
                for task in ('home_win','home_win_and_over','home_win_and_total_band'):
                    t=report['tasks'][task]
                    st.caption(f"{task.replace('_',' ')}: Brier {t['metrics']['binary_brier']['value']:.4f}; training-only constant baseline {t['training_constant_baseline']['binary_brier']['value']:.4f}; log loss {t['metrics']['log_loss']['value']:.4f}; calibration error {t['ece']:.1%}.")
                st.caption('Fixed total lines are statistical study targets, not observed sportsbook offers. Joint score assumptions and retrospective results do not establish current readiness or a betting advantage.')
    from intelligence.openliga import public_dataset
    dataset=public_dataset(w.store)
    if json.loads(dataset)['source_datasets']:
        st.caption('Contains information from [OpenLigaDB](https://www.openligadb.de/), available under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Team identities and result-date handling were normalized.')
        with st.expander('Open results source and reuse licence'):
            st.download_button('Download the OpenLigaDB source subset',dataset,file_name='openligadb-source-subset.json',mime='application/json',key='openliga-source-download')
            st.caption('Only the attributed public-source subset is included. Model records, private history and credentials are excluded.')


def render_score_research(store,safe,sizes=(2,3)):
    from intelligence.current_score_research import candidates
    from intelligence.prediction_accuracy import saved_for_display
    rows=saved_for_display(store,candidates(store))
    if not rows:return
    st.subheader('Same-game probability research · no sportsbook ticket')
    st.caption('Experimental score-model estimates account for shared-game outcomes. They are unapproved, and joint calibration is not independently validated.')
    for size in sizes:
        group=[r for r in rows if len(r['legs'])==size and r['research_eligible']]
        if not group:
            st.caption(f'No {size}-leg same-game candidate meets the research sample and uncertainty checks.');continue
        # Evidence checks first, then estimated winning probability within size.
        r=max(group,key=lambda x:(x['joint_probability'],-(x['upper']-x['lower'])))
        with st.container(border=True):
            st.text(safe(f"{size}-leg experimental SGP · {r['event']} · Bundesliga"))
            from intelligence.consumer_ui import friendly_time
            st.caption(friendly_time(r['kickoff']))
            for leg in r['legs']:
                market={'h2h':'Match winner','btts':'Both teams to score','totals':'Total goals'}[leg['market']]
                text=market+' · '+leg['selection']+(f" {leg['point']}" if leg['point'] is not None else '')
                st.text(safe(f"{text} · score-model estimate {leg['probability']:.1%}"))
            st.write(f"Combined model estimate **{r['joint_probability']:.1%}** · model-implied fair decimal **{r['fair_odds']:.2f}**")
            st.caption(f"Historical calibration range {r['lower']:.1%}–{r['upper']:.1%}; not an event-specific confidence interval. No quoted combined odds or EV.")
            st.caption('This combination has no demonstrated betting advantage; the historical joint test is descriptive and has not approved the model.')
            with st.expander(f"Evidence and risks for this {size}-leg combination"):
                st.caption(safe(r['probability_method']))
                st.caption(f"2025–26 test: {r['test_n']} games · Brier {r['test_metrics']['binary_brier']['value']:.4f}; simple score baseline {r['test_baseline']['binary_brier']['value']:.4f}. Calibration bucket: {r['calibration_bin_n']} earlier games.")
                if r['test_metrics']['binary_brier']['value']>=r['test_baseline']['binary_brier']['value']:
                    st.caption('This joint task did not beat the simple baseline on Brier score. Treat it as an inspection candidate, not evidence of an advantage.')
                st.caption('Source checked '+r['source_observed_at'])
                st.caption('Recorded before kickoff · '+friendly_time(r['recorded_at']))
                for limitation in r['limitations']:st.text(safe(limitation))
