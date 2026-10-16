"""Navigate preserved capabilities through the four-page registry in UI tests."""
from intelligence.navigation import TOOLS


def navigate(app,target):
    if target in {t.name for t in TOOLS}:
        app.sidebar.radio[0].set_value('Settings & Research Tools').run()
        next(s for s in app.selectbox if s.key=='research_tool').set_value(target).run()
    else:
        page='Best Picks & Parlays' if target in ('Best Selections by Game','Best Opportunities','Daily Parlay Research','AI Parlay Builder') else target
        app.sidebar.radio[0].set_value(page).run()
    assert not app.exception,target
    return app
