"""Actual ledger performance and separately labeled model research diagnostics."""
import pandas as pd
import streamlit as st
from intelligence.performance import metrics,breakdown
from intelligence.market_validation import load_reports


def render_publications(store):
    origin=st.radio('Record type',['forward','backtest'],horizontal=True,key='performance_origin')
    records=store.records(origin); summary=metrics(records)
    a,b,c=st.columns(3)
    a.metric('Published predictions',summary['published']);b.metric('Completed outcomes',summary['settled']);c.metric('Pending',summary['pending'])
    st.caption('Forward publications and backtests are separated. A research candidate is not a published prediction. Forecast classification accuracy is not a betting win rate.')
    if not records:
        st.info('No published predictions in this ledger. Performance metrics will appear only after genuine publications and evidence-backed settlements.')
    else:
        a,b,c,d=st.columns(4)
        a.metric('Wins',summary['wins']);b.metric('Losses',summary['losses'])
        c.metric('Pushes',summary['pushes']);d.metric('Voids',summary['voids'])
        st.caption(f"Decisive sample: {summary['decisive_sample']}. Win rate: "+(f"{summary['win_rate']:.1%}" if summary['win_rate'] is not None else 'unavailable')+'. One hypothetical unit per publication; no accepted-ticket or profitability claim.')
        with st.expander('Return, drawdown and calibration details'):
            st.json(summary)
        dimension=st.selectbox('Break down by',['sport','market','model_version','parlay_size'])
        st.json(breakdown(records,dimension))
        st.dataframe(pd.DataFrame([{'Published':r['at'],'Sport':r['payload']['quote']['sport'],
            'Event':r['payload']['quote']['event'],'Selection':r['payload']['quote']['selection'],
            'Outcome':r['outcome'],'Result evidence':r['source']} for r in records]),hide_index=True,use_container_width=True)
        if summary['calibration']:
            st.caption('Forward calibration with bin sample sizes. Frequency intervals assume independence; overlapping predictions can violate that assumption.')
            st.table(summary['calibration'])
    by_size=breakdown(records,'parlay_size')
    st.table([{'Legs':n,'Published':by_size.get(str(n),{}).get('published',0),
        'Settled':by_size.get(str(n),{}).get('settled',0),
        'Observed win rate':by_size.get(str(n),{}).get('win_rate'),
        'Hypothetical ROI':by_size.get(str(n),{}).get('roi')} for n in (1,2,3)])
    st.caption('Empty 2/3-leg groups have no parlay performance evidence. Win rates include decisive outcomes only; pushes return stake and voids are excluded from turnover. One hypothetical unit per publication. Recorded losses remain included.')
    st.caption('Win-rate Wilson intervals are suppressed for shared-event decisions. ROI intervals require at least 30 UTC-day blocks and use a day-block bootstrap; between-day dependence/stationarity remain unverified. Prices are publication observations, not confirmed accepted/placed tickets. Slippage, taxes and operator rules are not inferred.')


def render_evaluations(store):
    st.subheader('Held-out forecast research — separate from betting results')
    from intelligence.epl_forecasts import load_artifact
    focused=load_artifact()
    if focused:
        with st.expander('Premier League calibrated BTTS / goals 2.5 — research only'):
            st.caption('Training through June 2023; calibration July 2023–June 2024; primary test July 2024–June 2025. Later periods monitor partial-coverage drift. Binary Brier convention: (p − outcome)², unlike the two-class scores below.')
            st.json({'coverage':focused['coverage'],'markets':focused['tasks'],
                     'limitations':focused['limitations'],'source':focused['source'],
                     'sources':focused['sources'],'approved':False,'betting_roi':None})
    reports=load_reports()
    if not reports:
        st.info('No current code-matching advanced-market evaluation reports are available.')
    for report in reports:
        with st.expander(f'{report["sport"]} · {report["model_version"]} · research only'):
            st.write(f'Genuine data through {report["data_end"]}. Calibration starts {report["calibration_start"]}; held-out scoring period starts {report["test_start"]}. Source: {report["data_source"]}')
            st.caption('Predeclared fixed thresholds, not observed historical sportsbook lines. Accuracy means event-label classification, not the percentage of profitable bets. No historical ROI/P&L or validated advantage is available.')
            st.caption('These archive periods were also used for earlier baseline research. This is exploratory out-of-sample scoring, not independent confirmation; model selection needs a fresh locked test period.')
            rows=[]
            for t in report['tasks']:
                rows.append({'Market':t['market'],'Diagnostic selection':t['selection_rule'],
                    'Fixed threshold (not sportsbook line)':t['fixed_diagnostic_line'],
                    'Calibration n':t['calibration_n'],'Test n':t['test_n'],
                    'Classification accuracy':t['classification_accuracy'],'Accuracy interval (IID assumption)':t['accuracy_interval'],
                    'Simple-baseline accuracy':t['baseline_classification_accuracy'],
                    'Positive-class rate':t['test_positive_rate'],
                    'Two-class Brier':t['metrics']['brier'],'Log loss':t['metrics']['log_loss'],
                    'Baseline Brier':t['simple_baseline_metrics']['brier'],
                    'Calibration gap':t['calibration_gap'],'ROI':'Unavailable: no observed prices/restrictions'})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            st.caption(report['score_convention']+'. '+report['interval_assumptions'])
            st.json({'publication_blockers':report['promotion_blockers']})
    st.warning('Persistent storage and backups are required before subscribers rely on this ledger. Existing publication/settlement records remain immutable; research diagnostics never replace forward results.')


def render_performance(store):
    paper,published,evaluations=st.tabs(['Prospective paper research','Published hypothetical records','Held-out model evaluations'])
    with paper:
        from intelligence.processing import shadow_statistics
        summary=shadow_statistics(store)
        a,b=st.columns(2);c,d=st.columns(2)
        a.metric('Paper forecasts recorded',summary['private_forecasts'])
        b.metric('Paper forecasts with result labels',summary['scored_forecast_labels'])
        groups=summary['by_sport_market_model']
        c.metric('Paper target hits',sum(r['hits'] for r in groups.values()))
        d.metric('Paper target misses',sum(r['misses'] for r in groups.values()))
        st.caption('Immutable forecasts actually recorded before kickoff. Backtests are separate. Source-target hits/misses are not accepted sportsbook wins/losses or betting profitability; shared events and selections are dependent.')
        with st.expander('Private forward research forecasts — not betting performance'):
            st.json(summary)
        if not summary['private_forecasts']:
            st.info('No prospective paper forecasts have been recorded. Historical test matches are not counted as paper results.')
    with published:
        render_publications(store)
    with evaluations:
        render_evaluations(store)
