"""Synthetic credentials only. Invalid config never reaches a transport."""
from dataclasses import replace
from unittest.mock import patch
from pathlib import Path
import json,sys
import pytest
from intelligence.shared_state import Config,Client,StateError,public_failure,configuration
from test_shared_control import CONFIG,WRITER,READER,TOKEN


@pytest.mark.parametrize('suffix',['','/','/rest/v1','/rest/v1/'])
def test_official_project_and_rest_urls_produce_one_rpc_prefix(suffix):
    c=replace(CONFIG,url='  '+CONFIG.url+suffix+'\n')
    assert c.url==CONFIG.url and c.problem(writer=True) is None
    calls=[]
    class Response:
        status_code=200
        def iter_content(self,n):yield b'{"generation":1}'
        def close(self):pass
    class Session:
        def post(self,url,**kwargs):
            calls.append(url)
            assert kwargs['headers']['apikey']==WRITER
            assert kwargs['allow_redirects'] is False
            return Response()
    assert Client(c,writer=True,session=Session()).read()=={'generation':1}
    assert calls==[CONFIG.url+'/rest/v1/rpc/research_state_view']


@pytest.mark.parametrize('url',[
    'http://'+'a'*20+'.supabase.co',
    'https://'+'a'*20+'.supabase.co.evil.test/rest/v1/',
    'https://'+'a'*20+'.supabase.co:443/rest/v1/',
    'https://user:synthetic-password@'+'a'*20+'.supabase.co/rest/v1/',
    CONFIG.url+'/other/path',CONFIG.url+'/rest/v1/?token=synthetic-private-token',
    CONFIG.url+'/rest/v1/#fragment',CONFIG.url+'/rest/v1//',
    'https://supabase.com/dashboard/project/synthetic-project',
])
def test_arbitrary_hosts_ports_credentials_and_paths_stay_blocked(url):
    c=replace(CONFIG,url=url)
    with patch('intelligence.shared_state.requests.Session',side_effect=AssertionError('No HTTP')):
        with pytest.raises(StateError) as error:Client(c,writer=True).read()
    safe=public_failure(error.value)
    assert safe['error_code']=='supabase_origin_invalid'
    assert url not in str(safe) and 'synthetic-private-token' not in str(safe)


@pytest.mark.parametrize(('key','expected'),[
    ('','state_key_missing'),('sb_secret_synthetic_never_real','state_key_format_invalid'),
    (READER,'state_key_role_mismatch'),
])
def test_writer_key_diagnostics_reveal_only_the_configuration_category(key,expected):
    c=replace(CONFIG,service_key=key)
    with patch('intelligence.shared_state.requests.Session',side_effect=AssertionError('No HTTP')):
        with pytest.raises(StateError) as e:Client(c,writer=True).read()
    report=public_failure(e.value)
    assert report['error_code']==expected
    if key:assert key not in json.dumps(report)


def test_cli_reports_safe_url_failure_without_values_or_traceback(monkeypatch,capsys):
    from intelligence.background import main
    for k,v in {'RESEARCH_SHARED_STATE_ENABLED':'1','RESEARCH_STATE_USE_REVIEWED':'1',
        'RESEARCH_STATE_URL':CONFIG.url+'/rest/v1/?token=synthetic-private-token',
        'RESEARCH_STATE_SERVICE_KEY':WRITER,'RESEARCH_EXPECTED_STORE_INSTANCE':'a'*32}.items():monkeypatch.setenv(k,v)
    monkeypatch.setattr(sys,'argv',['background','--verify-shared'])
    with patch('intelligence.shared_state.requests.Session',side_effect=AssertionError('No HTTP')):
        with pytest.raises(SystemExit) as e:main()
    out=capsys.readouterr();assert e.value.code==1
    report=json.loads(out.out)
    assert report['error_code']=='supabase_origin_invalid'
    assert all(x not in out.out+out.err for x in (WRITER,'synthetic-private-token','Traceback',CONFIG.url))


@pytest.mark.parametrize('code',['synthetic-secret-not-a-code',None,[]])
def test_unknown_exception_codes_never_become_public_diagnostics(code):
    secret='synthetic-private-exception'
    report=public_failure(StateError(secret,code=code))
    assert report['error_code']=='configuration_storage_or_provider'
    assert secret not in json.dumps(report) and 'synthetic-secret-not-a-code' not in json.dumps(report)


def test_real_configuration_path_normalizes_copied_rest_endpoint(monkeypatch):
    monkeypatch.setenv('RESEARCH_STATE_URL',CONFIG.url+'/rest/v1/')
    assert configuration().url==CONFIG.url


def test_verify_workflow_message_is_constant_and_mode_specific():
    text=Path('deploy/private_worker.yml').read_text()
    assert 'Selected operation: verify. Two state reads; no remote writes or sports-provider requests.' in text
    assert 'echo "$RESEARCH_STATE_SERVICE_KEY"' not in text


@pytest.mark.parametrize(('status','code'),[(401,'shared_state_access_denied'),(403,'shared_state_access_denied'),
    (404,'shared_state_rpc_unavailable'),(429,'shared_state_service_unavailable'),
    (503,'shared_state_service_unavailable'),(400,'shared_state_http_failure')])
def test_http_failure_categories_never_read_or_log_response_bodies(status,code):
    class Response:
        status_code=status
        def iter_content(self,n):pytest.fail('Never read a failed response body that could contain credentials')
        def close(self):pass
    class Session:
        def post(self,*a,**k):return Response()
    with pytest.raises(StateError) as e:Client(CONFIG,writer=True,session=Session()).read()
    report=public_failure(e.value)
    assert report['error_code']==code and WRITER not in json.dumps(report)
