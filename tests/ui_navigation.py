"""Navigate preserved detailed tools after their move into owner settings.

Legacy names deliberately select the same detailed renderers as before. New
everyday-screen tests select the five actual sidebar pages directly.
"""
from intelligence.navigation import TOOLS


def navigate(app,target):
    aliases={'AI Dashboard':'Daily Research Audit','Best Picks & Parlays':'Detailed Picks & Parlays',
        'Performance Tracker':'Detailed Performance','Settings':'Connections & Data Settings',
        'Best Selections by Game':'Detailed Picks & Parlays','Best Opportunities':'Detailed Picks & Parlays',
        'Daily Parlay Research':'Detailed Picks & Parlays','AI Parlay Builder':'Detailed Picks & Parlays'}
    target=aliases.get(target,target)
    if target in {t.name for t in TOOLS}:
        app.sidebar.radio[0].set_value('Settings').run()
        next(s for s in app.selectbox if s.key=='research_tool').set_value(target).run()
    else:
        page='Settings' if target=='Settings & Research Tools' else target
        app.sidebar.radio[0].set_value(page).run()
    assert not app.exception,target
    return app
