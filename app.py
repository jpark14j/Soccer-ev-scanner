import streamlit as st
import pandas as pd
import itertools
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title='Soccer EV Scanner',page_icon='⚽',layout='wide')
st.title('⚽ Soccer EV Scanner')
st.caption('Toronto, Ontario • CAD • On-demand scanning • DraftKings Ontario target')
st.warning('Prototype: no live DraftKings Ontario feed is connected. Demo odds are fictional. Uploaded odds are user-provided, not verified. This app does not place bets.')

now=datetime.now(ZoneInfo('America/Toronto'))
demo=pd.DataFrame([
 {'event_id':'E1','kickoff':(now+timedelta(days=1)).isoformat(),'league':'Premier League','match':'Example FC vs Sample United','market':'Over/Under Goals','selection':'Over 2.5','book':'DraftKings Ontario','decimal_odds':2.25,'fair_probability':0.49},
 {'event_id':'E2','kickoff':(now+timedelta(days=2)).isoformat(),'league':'La Liga','match':'Demo Madrid vs Test Sevilla','market':'Both Teams to Score','selection':'Yes','book':'DraftKings Ontario','decimal_odds':2.10,'fair_probability':0.51},
 {'event_id':'E3','kickoff':(now+timedelta(days=3)).isoformat(),'league':'Serie A','match':'Example Milan vs Demo Roma','market':'Player Shots','selection':'Player A 2+ shots','book':'DraftKings Ontario','decimal_odds':1.95,'fair_probability':0.54},
 {'event_id':'E4','kickoff':(now+timedelta(days=4)).isoformat(),'league':'Bundesliga','match':'Sample Dortmund vs Test Leipzig','market':'Match Result','selection':'Home win','book':'DraftKings Ontario','decimal_odds':2.55,'fair_probability':0.42},
 {'event_id':'E5','kickoff':(now+timedelta(days=5)).isoformat(),'league':'Ligue 1','match':'Demo Paris vs Example Lyon','market':'Player Shots on Target','selection':'Player B 1+ SOT','book':'DraftKings Ontario','decimal_odds':1.85,'fair_probability':0.58},
 {'event_id':'E6','kickoff':(now+timedelta(days=6)).isoformat(),'league':'MLS','match':'Sample Toronto vs Demo Miami','market':'Match Corners','selection':'Over 8.5','book':'DraftKings Ontario','decimal_odds':2.05,'fair_probability':0.52},
])

st.sidebar.header('Scan settings')
source=st.sidebar.radio('Odds source',['Demo data','Upload odds CSV'])
window=st.sidebar.selectbox('Upcoming matches',['Today','Today + tomorrow','Next 7 days'],index=2)
min_ev=st.sidebar.slider('Minimum estimated EV (%)',-20.0,50.0,5.0,0.5)
max_legs=st.sidebar.slider('Maximum parlay legs',2,6,6)
st.sidebar.caption('Fair probability must be independently estimated. It cannot be inferred reliably from one bookmaker price alone.')

if source=='Upload odds CSV':
    upload=st.file_uploader('Upload a CSV with odds and your probability estimates',type='csv')
    st.download_button('Download CSV example',demo.to_csv(index=False).encode(),'soccer_odds_template.csv','text/csv')
    if upload is None:
        st.info('Upload a CSV to run a scan. Required columns: event_id, kickoff, league, match, market, selection, book, decimal_odds, fair_probability.')
        st.stop()
    try:
        data=pd.read_csv(upload)
    except Exception as e:
        st.error(f'Cannot read CSV: {e}'); st.stop()
else:
    data=demo.copy()

required=['event_id','kickoff','league','match','market','selection','book','decimal_odds','fair_probability']
missing=[c for c in required if c not in data.columns]
if missing:
    st.error('Missing columns: '+', '.join(missing)); st.stop()
try:
    data['kickoff']=pd.to_datetime(data['kickoff'],utc=True,errors='coerce').dt.tz_convert('America/Toronto')
    data['decimal_odds']=pd.to_numeric(data['decimal_odds'],errors='coerce')
    data['fair_probability']=pd.to_numeric(data['fair_probability'],errors='coerce')
except Exception as e:
    st.error(str(e)); st.stop()
invalid=data['kickoff'].isna()|~data['decimal_odds'].gt(1)|~data['fair_probability'].between(0,1,inclusive='neither')
if invalid.any():
    st.warning(f'{invalid.sum()} invalid row(s) excluded. Odds must exceed 1 and probability must be strictly between 0 and 1.')
    data=data.loc[~invalid].copy()

start=now.date()
end=start+timedelta(days={'Today':0,'Today + tomorrow':1,'Next 7 days':6}[window])
data=data[(data['kickoff'].dt.date>=start)&(data['kickoff'].dt.date<=end)].copy()
leagues=st.multiselect('Leagues',sorted(data['league'].dropna().unique()),default=sorted(data['league'].dropna().unique()))
data=data[data['league'].isin(leagues)]

if st.button('🔍 Find +EV Bets',type='primary',use_container_width=True):
    st.session_state['scanned']=True
if not st.session_state.get('scanned',False):
    st.info('Select your settings, then press Find +EV Bets. No scanning occurs in the background.')
    st.stop()

data['EV %']=(data['fair_probability']*data['decimal_odds']-1)*100
data['Break-even %']=100/data['decimal_odds']
qualifying=data[data['EV %']>=min_ev].sort_values('EV %',ascending=False)

single,parlays,about=st.tabs(['Singles & player props','Parlays','Method & limitations'])
with single:
    st.subheader(f'{len(qualifying)} qualifying single bets')
    if qualifying.empty: st.info('No bets match the current EV threshold.')
    else:
        display=qualifying.copy()
        display['Kickoff (Toronto)']=display['kickoff'].dt.strftime('%b %d, %I:%M %p')
        display['Estimated win %']=display['fair_probability']*100
        st.dataframe(display[['Kickoff (Toronto)','league','match','market','selection','book','decimal_odds','Estimated win %','Break-even %','EV %']].round(2),hide_index=True,use_container_width=True)
        st.download_button('Download singles CSV',qualifying.to_csv(index=False).encode(),'singles.csv','text/csv')
with parlays:
    st.subheader('Independent-event parlay estimates')
    st.caption('Only combines legs from different event IDs. This avoids obvious same-match correlation, but does not prove independence. Actual DraftKings parlay acceptance and payout must be checked.')
    st.warning('Parlay calculations use the product of individual decimal odds as an indicative price, NOT a verified sportsbook quote. Do not treat these as executable opportunities.')
    rows=[]
    # keep combinations bounded for mobile use
    candidates=qualifying.head(20).to_dict('records')
    for n in range(2,max_legs+1):
        for combo in itertools.combinations(candidates,n):
            if len({str(x['event_id']) for x in combo})<n: continue
            prob=1.0; odds=1.0
            for x in combo:
                prob*=float(x['fair_probability']); odds*=float(x['decimal_odds'])
            ev=(prob*odds-1)*100
            if ev>=min_ev:
                rows.append({'Legs':n,'Selections':' | '.join(f"{x['match']}: {x['selection']}" for x in combo),'Indicative decimal odds':round(odds,2),'Estimated win %':round(prob*100,2),'Indicative EV %':round(ev,2)})
    if rows:
        parlay_df=pd.DataFrame(rows).sort_values('Indicative EV %',ascending=False).head(100)
        st.dataframe(parlay_df,hide_index=True,use_container_width=True)
        st.download_button('Download indicative parlays CSV',parlay_df.to_csv(index=False).encode(),'parlays.csv','text/csv')
    else: st.info('No eligible combinations under current settings.')
with about:
    st.markdown('''**EV formula:** `(estimated win probability × decimal odds − 1) × 100`.

**Probability estimates:** The `fair_probability` field must come from a separate, validated statistical model or an appropriately de-vigged reference market. This prototype does not generate true probabilities with AI.

**Live integration:** A licensed data provider must be verified for **DraftKings Ontario** and each desired soccer market, especially player props. The scanner cannot claim live coverage until that integration exists.

**Parlays:** Same-game combinations are excluded. Different games can still be statistically dependent. Indicative odds may not match a sportsbook's actual parlay quote. Six-leg parlays can have very low win probabilities even when estimated EV is positive.

**Privacy and safety:** No account credentials or betting transactions are collected. Results are research estimates, not guaranteed returns.''')
