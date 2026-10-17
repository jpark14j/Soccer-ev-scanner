import streamlit as st
from intelligence.bankroll import analyze
from intelligence.ev import qualify
from intelligence.markets import selection_label


@st.fragment(run_every='60s')
def render_bankroll(opportunities):
    if not st.checkbox('Enable hypothetical bankroll analysis',key='risk_enable'):
        return
    st.caption('CAD illustrations only. No wager is placed. A limit is a chosen loss budget, not evidence of a profitable strategy.')
    bankroll=st.number_input('Hypothetical bankroll (CAD)',min_value=1.,max_value=1_000_000.,value=1000.,step=100.,key='risk_bankroll')
    eligible=[o for o in opportunities if qualify(o.quote,o.estimate)[0]]
    selected=st.selectbox('Validated single for optional Kelly',['Loss scenarios only',*range(len(eligible))],
        format_func=lambda i:selection_label(eligible[i].quote) if isinstance(i,int) else i,key='risk_selection')
    kwargs={}
    if isinstance(selected,int):
        o=eligible[selected]
        kwargs={'odds':o.quote.odds,'probability':o.estimate.probability,'lower':o.estimate.lower,
                'upper':o.estimate.upper,'validated':True,'price_verified':True}
    result=analyze(bankroll,**kwargs)
    st.table([{'Stake %':f'{row["stake_fraction"]:.2%}','Stake / maximum loss (CAD)':f'{row["stake"]:.2f}',
        'Three losses (CAD)':f'{row["three_equal_stakes_maximum_loss"]:.2f}',
        'Above 0.5% per-bet cap':row['exceeds_per_bet_cap'],'Three stakes above 2% portfolio cap':row['exceeds_portfolio_cap_for_three']}
        for row in result['scenarios']])
    st.write(result['reason'])
    if result['kelly_amount'] is not None:
        st.write(f'Hypothetical capped amount: CAD {result["kelly_amount"]:.2f}. Recheck source times; an observed price is not guaranteed execution.')
        st.table(result['sensitivity'])
    st.caption('Research parlays have no validated joint probability or actual combined quote, so Kelly is disabled for them. Overlapping parlays can concentrate exposure; adding tickets does not diversify it. The example caps (0.5% per bet, 2% overall) are conservative assumptions, not personalized advice.')
