"""Free local rule-based answers from the same evidence used by the SDK adapter."""
from intelligence.analyst_context import build_context, model_evaluations, render_plan, select_local


def answer(question, analysis, performance=None, now=None):
    context = build_context(analysis,performance,model_evaluations(),now)
    return render_plan(select_local(question,context),context)[0]
