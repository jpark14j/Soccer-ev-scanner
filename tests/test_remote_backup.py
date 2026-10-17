"""In-memory fake storage transport only; never a real account or upload."""
from dataclasses import replace
from datetime import timedelta
import json,sqlite3
import pytest
import requests
from conftest import NOW
from intelligence.remote_backup import Config,BackupError,upload,restore,status,LIMIT
from intelligence.storage import Store
from intelligence.current_results import _reserve
from intelligence.request_guard import reviewed_release

KEY='eyJsyntheticHEADER.onlySyntheticPAYLOAD.onlySyntheticSIGNATURE'
CONFIG=Config(True,True,'https://'+'a'*20+'.supabase.co','research-private',KEY)


class Response:
    def __init__(self,raw=b'',status=200):self.raw,self.status_code=raw,status
    def iter_content(self,size):
        for start in range(0,len(self.raw),size):yield self.raw[start:start+size]
    def close(self):pass


class Session:
    def __init__(self):self.calls=[];self.objects={};self.public=False;self.corrupt=False
    def get(self,url,**kwargs):
        self.calls.append(('GET',url));assert kwargs['allow_redirects'] is False
        assert kwargs['headers']['Authorization']=='Bearer '+KEY
        if '/bucket/' in url:return Response(json.dumps({'id':CONFIG.bucket,'public':self.public}).encode())
        name=url.split('/'+CONFIG.bucket+'/',1)[1]
        raw=self.objects[name]
        return Response(raw+b'corruption' if self.corrupt else raw)
    def post(self,url,**kwargs):
        self.calls.append(('POST',url));assert kwargs['headers']['x-upsert']=='false'
        assert kwargs['allow_redirects'] is False
        self.objects[url.split('/'+CONFIG.bucket+'/',1)[1]]=kwargs['data']
        return Response(status=201)


def test_default_disabled_and_status_never_contact_a_service(store):
    s=Session()
    assert not status(store,Config())['configured'] and not s.calls
    with pytest.raises(BackupError,match='disabled'):upload(store,Config(),s,NOW)
    assert not s.calls and KEY not in repr(CONFIG)


def test_private_roundtrip_preserves_records_budgets_and_recovery_hold(store,quote,opportunity,tmp_path):
    store.publish(opportunity,now=NOW);assert store.reserve(8,9,NOW)
    assert _reserve(store,NOW)
    s=Session();receipt=upload(store,CONFIG,s,NOW)
    assert len(s.calls)==3 and receipt['off_host_byte_roundtrip_verified'] and not receipt['continuous_durability_verified']
    assert KEY not in str(receipt)
    path=tmp_path/'new-restored.sqlite3'
    result=restore(receipt['object_reference'],path,CONFIG,s)
    assert result['requests_blocked_until_review'] and not result['active_database_changed']
    recovered=Store(path)
    assert len(recovered.records())==1 and not recovered.reserve(1,9,NOW) and not _reserve(recovered,NOW)
    assert not recovered.reserve(1,9,NOW+timedelta(days=1)) and not _reserve(recovered,NOW+timedelta(days=1))
    from intelligence.quota import quota_details,refresh_reason
    quota=quota_details(recovered,9,NOW+timedelta(days=1))
    assert quota['recovery_hold'] and quota['remaining']==0
    assert 'does not release' in refresh_reason(key_configured=True,selection_count=1,cost=1,quota=quota)
    with recovered.connect() as db:
        assert db.execute('SELECT used FROM budget WHERE day=?',(NOW.date().isoformat(),)).fetchone()[0]==8
        assert db.execute('SELECT count(*) FROM backup_model_assets').fetchone()[0]>=9
    reviewed_release(recovered,9,6,'https://example.test/operator-review',NOW)
    assert not recovered.reserve(1,9,NOW) and not _reserve(recovered,NOW)
    assert store.reserve(1,9,NOW)  # Original store unchanged by restoration.
    before=len(s.calls)
    with pytest.raises(BackupError,match='existing/active'):restore(receipt['object_reference'],store.path,CONFIG,s)
    assert len(s.calls)==before
    with pytest.raises(BackupError,match='One manual'):upload(store,CONFIG,s,NOW)


def test_public_bucket_is_rejected_before_upload(store):
    s=Session();s.public=True
    with pytest.raises(BackupError,match='private bucket'):upload(store,CONFIG,s,NOW)
    assert len(s.calls)==1 and not s.objects


def test_corrupt_readback_has_no_success_receipt_and_restore_creates_no_file(store,tmp_path):
    s=Session();s.corrupt=True
    with pytest.raises(BackupError,match='checksum'):upload(store,CONFIG,s,NOW)
    assert status(store,CONFIG)['latest_receipt'] is None
    name=next(iter(s.objects));target=tmp_path/'corrupt.sqlite3'
    with pytest.raises(BackupError,match='checksum'):restore(name,target,CONFIG,s)
    assert not target.exists()


@pytest.mark.parametrize('url',['http://localhost','https://127.0.0.1','https://a.supabase.co','https://'+('a'*20)+'.supabase.co/extra','https://user:password@'+('a'*20)+'.supabase.co','https://[invalid'])
def test_unreviewed_or_arbitrary_origins_never_receive_credentials(store,url):
    s=Session()
    with pytest.raises(BackupError):upload(store,replace(CONFIG,url=url),s,NOW)
    assert not s.calls


def test_transport_error_does_not_expose_secrets(store):
    s=Session()
    def fail(*args,**kwargs):raise requests.ConnectionError(KEY)
    s.get=fail
    with pytest.raises(BackupError) as error:upload(store,CONFIG,s,NOW)
    assert KEY not in str(error.value)


def test_readback_size_is_bounded_and_redirects_are_not_followed(store):
    s=Session()
    original=s.get
    def oversized(url,**kwargs):
        if '/bucket/' in url:return original(url,**kwargs)
        return Response(b'x'*(LIMIT+1))
    s.get=oversized
    with pytest.raises(BackupError,match='20 MiB'):upload(store,CONFIG,s,NOW)


def test_backup_key_is_redacted_from_chat_and_configuration(monkeypatch):
    from intelligence.analyst_config import load_config
    from intelligence.chat_privacy import redact,validate_input,InvalidChatInput
    monkeypatch.setenv('RESEARCH_BACKUP_SERVICE_KEY',KEY)
    config=load_config()
    assert KEY in config.sensitive_values and KEY not in redact(KEY,config.sensitive_values)
    with pytest.raises(InvalidChatInput):validate_input('Here is '+KEY,config)


def test_online_worker_stays_disabled_even_with_unverified_attestations(store,monkeypatch):
    from intelligence.worker import run_cycle
    for name in ('RESEARCH_WORKER_ENABLED','RESEARCH_DURABLE_STORAGE_VERIFIED','RESEARCH_DATA_RIGHTS_VERIFIED'):monkeypatch.setenv(name,'1')
    with pytest.raises(ValueError,match='shared transactional budget'):run_cycle(store,['NBA'],offline=False)
