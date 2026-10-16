from intelligence.llm import PaidAnalyst
from intelligence.pipeline import Analysis


def test_paid_calls_disabled_without_explicit_approval(store,opportunity):
    class Session:
        def post(self,*a,**k): raise AssertionError('No paid calls authorized')
    result=PaidAnalyst(store,'secret',False,session=Session()).respond('best NBA',Analysis(opportunities=[opportunity]))
    assert isinstance(result,str)


def test_budget_blocks_call_before_transport(store,opportunity):
    class Session:
        def post(self,*a,**k): raise AssertionError('Budget exhausted')
    result=PaidAnalyst(store,'secret',True,monthly_cap=0,session=Session()).respond('best NBA',Analysis(opportunities=[opportunity]))
    assert 'budget reached' in result


def test_model_can_route_but_not_introduce_invented_odds(store,opportunity):
    class Response:
        status_code=200
        def json(self): return {'choices':[{'message':{'content':'{"intent":"best","sport":"NBA","odds":99}'}}]}
    class Session:
        def post(self,*a,**k): return Response()
    result=PaidAnalyst(store,'secret',True,session=Session()).respond('best NBA',Analysis(opportunities=[opportunity]))
    assert '99' not in result and 'unavailable' in result


def test_no_paid_calls_without_analytical_records(store):
    result=PaidAnalyst(store,'secret',True).respond('best picks',Analysis())
    assert 'No current opportunities' in result
