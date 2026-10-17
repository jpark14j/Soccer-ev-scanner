"""Optional fenced single-writer snapshots, NOT a multi-writer SQLite database.

Postgres commits the head and reserves provider costs independently of snapshots.
No network on import/configuration/status. Explicit pull/worker only; disabled.
"""
from contextlib import closing
from dataclasses import dataclass,field
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import base64,gzip,io,json,os,re,sqlite3,tempfile,threading
import requests
from intelligence.domain import utcnow,parse_time
from intelligence.remote_backup import _assets,_valid
from intelligence.persistence import backup_store

MAX_RAW=64*1024*1024
MAX_COMPRESSED=4*1024*1024
MAX_RESPONSE=7*1024*1024


CONFIG_FAILURES={
    'shared_state_disabled':'RESEARCH_SHARED_STATE_ENABLED must be 1 for this explicit state operation.',
    'shared_state_review_required':'Review shared snapshot use before setting RESEARCH_STATE_USE_REVIEWED=1.',
    'supabase_origin_invalid':'Set RESEARCH_STATE_URL to the official HTTPS project origin; arbitrary paths, queries, ports and other hosts are refused.',
    'state_key_missing':'Configure the required state key in server-side Secrets. Never paste credentials into chat or logs.',
    'state_key_format_invalid':'This adapter requires the existing project legacy JWT key in server-side Secrets, not a new-format key.',
    'state_key_role_mismatch':'The worker requires the legacy service_role JWT; the preview reader requires the anon JWT. Keep the writer key out of the preview.',
    'state_reader_token_invalid':'Configure the original private reader token in preview Secrets; do not print or share it.',
    'state_configuration_invalid':'Inspect private shared-state settings. No credential values are logged.',
    'shared_state_access_denied':'Supabase denied state access. Privately check the project/key match, legacy JWT role and RPC permissions; do not share credentials.',
    'shared_state_rpc_unavailable':'Check that the shipping migration and state RPC exist and the project Data API exposes public. Do not loosen table permissions.',
    'shared_state_service_unavailable':'Supabase is unavailable or rate limited. Check project service health privately; no sports request is authorized.',
    'shared_state_http_failure':'The state endpoint rejected the request. Inspect private service configuration; no response body or credentials are logged.',
}


class StateError(ValueError):
    def __init__(self,message,*,code=None):
        super().__init__(message);self.code=code


def public_failure(error):
    """Only allowlisted codes/actions; never echo arbitrary exception text."""
    code=getattr(error,'code',None) if isinstance(error,StateError) else None
    if isinstance(code,str) and code in CONFIG_FAILURES:return {'error_code':code,'action':CONFIG_FAILURES[code]}
    return {'error_code':'configuration_storage_or_provider',
        'action':'Inspect private configuration and saved heartbeat. No credentials or raw exception text are logged.'}


@dataclass(frozen=True)
class Config:
    enabled:bool=False
    reviewed:bool=False
    url:str=''
    reader_key:str=field(default='',repr=False)
    reader_token:str=field(default='',repr=False)
    service_key:str=field(default='',repr=False)

    def __post_init__(self):
        # Supabase exposes both Project URL and REST API URL in its dashboard.
        # Normalize only these exact forms on the already allowed official host.
        # Never salvage a URL with credentials, ports, queries or arbitrary paths.
        m=re.fullmatch(r'(https://[a-z0-9]{20}\.supabase\.co)(?:/|/rest/v1/?)?',self.url.strip())
        if m:object.__setattr__(self,'url',m.group(1))

    def problem(self,writer=False):
        if not self.enabled:return 'Shared research state is disabled'
        if not self.reviewed:return 'Review free-tier limits, provider terms and snapshot privacy before activation'
        if not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co',self.url):return 'Configure an official HTTPS Supabase project origin'
        key=self.service_key if writer else self.reader_key
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}',key) or len(key)>4096:return 'Configure the server-only writer service-role or reader anon JWT in the appropriate Secrets'
        try:
            encoded=key.split('.')[1]
            role=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4))).get('role')
        except (ValueError,TypeError,AttributeError):return 'Invalid legacy project JWT format'
        if role!=('service_role' if writer else 'anon'):return 'Use the service-role JWT only in the independent writer and the anon JWT only in the preview reader'
        if not writer and not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',self.reader_token):return 'Configure a private high-entropy research reader token'
        return None

    def problem_code(self,writer=False):
        problem=self.problem(writer)
        if not problem:return None
        if not self.enabled:return 'shared_state_disabled'
        if not self.reviewed:return 'shared_state_review_required'
        if not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co',self.url):return 'supabase_origin_invalid'
        if not (self.service_key if writer else self.reader_key):return 'state_key_missing'
        if problem=='Use the service-role JWT only in the independent writer and the anon JWT only in the preview reader':return 'state_key_role_mismatch'
        if problem=='Configure a private high-entropy research reader token':return 'state_reader_token_invalid'
        if problem in ('Invalid legacy project JWT format','Configure the server-only writer service-role or reader anon JWT in the appropriate Secrets'):return 'state_key_format_invalid'
        return 'state_configuration_invalid'


def configuration(getter=None):
    def get(name,default=''):
        value=os.getenv(name)
        if value is None and getter:value=getter(name)
        return str(value or default)
    return Config(get('RESEARCH_SHARED_STATE_ENABLED','0')=='1',get('RESEARCH_STATE_USE_REVIEWED','0')=='1',
        get('RESEARCH_STATE_URL'),get('RESEARCH_STATE_READER_KEY'),get('RESEARCH_STATE_READ_TOKEN'),get('RESEARCH_STATE_SERVICE_KEY'))


class Client:
    def __init__(self,config,*,writer=False,session=None):
        self.config=config;self.writer=writer;self.session=session
        self.owner=uuid4().hex;self.fence=0;self.generation=0;self.local=threading.local()
        self.held=False

    def rpc(self,name,data):
        problem=self.config.problem(self.writer)
        if problem:raise StateError(problem,code=self.config.problem_code(self.writer))
        if name not in ('research_state_read','research_control','research_state_view'):raise StateError('Unsupported state operation')
        if name!='research_state_read' and not self.writer:raise StateError('Read-only replica cannot write shared state')
        session=self.session or requests.Session();key=self.config.service_key if self.writer else self.config.reader_key
        try:
            response=session.post(self.config.url+'/rest/v1/rpc/'+name,json=data,
                headers={'apikey':key,'Authorization':'Bearer '+key},timeout=(5,30),allow_redirects=False,stream=True)
            try:
                if response.status_code!=200:
                    status=response.status_code
                    code=('shared_state_access_denied' if status in (401,403) else
                        'shared_state_rpc_unavailable' if status==404 else
                        'shared_state_service_unavailable' if status==429 or status>=500 else 'shared_state_http_failure')
                    raise StateError('Shared-state request failed; check migration, access and service health privately',code=code)
                chunks=[];size=0
                for chunk in response.iter_content(65536):
                    size+=len(chunk)
                    if size>MAX_RESPONSE:raise StateError('Shared-state response exceeds bounded capacity')
                    chunks.append(chunk)
                raw=b''.join(chunks)
                if any(v and v.encode() in raw for v in (key,self.config.reader_token)):raise StateError('Credential reflected by state service')
                value=json.loads(raw)
                if not isinstance(value,dict):raise StateError('Invalid shared-state response')
                return value
            finally:response.close()
        except StateError:raise
        except (requests.RequestException,OSError,ValueError,TypeError):raise StateError('Shared-state transport or schema failure; no provider request authorized') from None
        finally:
            if self.session is None:session.close()

    def control(self,action,data=None):
        result=self.rpc('research_control',{'p_action':action,'p_owner':self.owner,'p_fence':self.fence,'p_data':data or {}})
        if result.get('ok') is not True:raise StateError('Shared-state operation blocked: '+str(result.get('code','unavailable')) if result.get('code') in
            {'duplicate_run','writer_busy','lease_lost','daily_budget','budget_hold_or_day_boundary','reservation_already_consumed','generation_conflict','missed_pregame_commit','unknown_cost_hold','unexpected_cost_hold'} else 'Shared-state operation blocked')
        return result

    def acquire(self,run_id):
        result=self.control('acquire',{'run_id':run_id})
        self.fence=result['fence'];self.generation=result['generation']
        self.held=result.get('held',True)
        return result

    def read(self):return self.rpc('research_state_view',{}) if self.writer else self.rpc('research_state_read',{'p_token':self.config.reader_token})

    def reserve(self,provider,cost):
        if self.held:return None
        rid=uuid4().hex
        try:result=self.control('reserve',{'provider':provider,'cost':cost,'id':rid})
        except StateError:return None
        self.local.reservation=rid
        return result

    def charge(self,actual):
        try:
            if type(actual) is not int or not 0<=actual<=10000:return self.control('cost_unknown')
            return self.control('charge',{'id':getattr(self.local,'reservation',''),'actual':actual})
        except StateError:
            self.held=True
            return None


def snapshot(store):
    with tempfile.TemporaryDirectory(prefix='shared-snapshot-') as folder:
        path=Path(folder)/'state.sqlite3';backup_store(store,path);_assets(path);_valid(path)
        if path.stat().st_size>MAX_RAW:raise StateError('Shared snapshot exceeds 64 MiB; migrate capacity before continuing')
        raw=path.read_bytes();compressed=gzip.compress(raw,mtime=0)
        if len(compressed)>MAX_COMPRESSED:raise StateError('Compressed shared snapshot exceeds 4 MiB')
        with closing(sqlite3.connect(path)) as db:identity=db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]
    return {'manifest':{'format':'research-single-writer-1','sha256':sha256(raw).hexdigest(),
        'compressed_sha256':sha256(compressed).hexdigest(),'bytes':len(raw),'store_instance':identity},
        'compressed':base64.b64encode(compressed).decode()}


def materialize(envelope,target):
    """New private file only. Remote authoritative budgets are never inferred here."""
    s=envelope.get('snapshot');target=Path(target)
    if not s or s.get('generation')!=envelope.get('generation'):raise StateError('No committed shared snapshot; explicit bootstrap is required')
    m=s['manifest']
    if m.get('format')!='research-single-writer-1' or len(s['compressed'])>6000000:raise StateError('Invalid snapshot manifest')
    try:
        compressed=base64.b64decode(s['compressed'],validate=True)
        if len(compressed)>MAX_COMPRESSED or sha256(compressed).hexdigest()!=m['compressed_sha256']:raise StateError('Compressed snapshot checksum differs')
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:raw=stream.read(MAX_RAW+1)
        if len(raw)>MAX_RAW or len(raw)!=m['bytes'] or sha256(raw).hexdigest()!=m['sha256']:raise StateError('Snapshot size/checksum differs')
        target.parent.mkdir(parents=True,exist_ok=True)
        with os.fdopen(os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as stream:stream.write(raw)
        try:
            _valid(target)
            with closing(sqlite3.connect(target)) as db:
                if db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]!=m['store_instance']:raise StateError('Snapshot store identity differs')
        except Exception:
            target.unlink(missing_ok=True);raise
    except StateError:raise
    except (OSError,ValueError,KeyError,sqlite3.Error):raise StateError('Shared snapshot validation failed; existing successful replica retained') from None
    return target


def hydrate_budgets(store,envelope):
    """Remote write-ahead reservations can be newer than the last SQLite head."""
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS football_data_requests(at TEXT NOT NULL)')
        for row in envelope.get('budgets',[]):
            day=row['day'];used=row['used']
            if type(used) is not int or used<0:raise StateError('Invalid remote budget')
            if row['provider']=='odds':
                db.execute('INSERT INTO budget VALUES(?,?) ON CONFLICT(day) DO UPDATE SET used=max(budget.used,excluded.used)',(day,used))
            elif row['provider']=='results':
                n=db.execute('SELECT count(*) FROM football_data_requests WHERE substr(at,1,10)=?',(day,)).fetchone()[0]
                db.executemany('INSERT INTO football_data_requests VALUES(?)',[(day+'T00:00:00+00:00',)]*max(0,min(6,used)-n))
    from intelligence.publication_journal import ensure
    ensure(store)
    with store.connect() as db:
        for r in envelope.get('publication_receipts',[]):
            db.execute('INSERT OR IGNORE INTO shared_publication_receipts VALUES(?,?,?)',(r['id'],r['at'],r['generation']))


def pull_replica(directory,config=None,client=None):
    """Explicit state-only network sync. Never sports-provider I/O or auto-restore."""
    c=config or configuration();client=client or Client(c);envelope=client.read()
    if not envelope.get('snapshot'):raise StateError('Shared state has not been bootstrapped')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    name='generation-'+str(int(envelope['generation']))+'-'+envelope['snapshot']['manifest']['sha256'][:16]+'.sqlite3'
    target=directory/name
    # Keep committed replica bytes pristine; the app uses a separate local copy.
    if not target.exists():materialize(envelope,target)
    else:
        if sha256(target.read_bytes()).hexdigest()!=envelope['snapshot']['manifest']['sha256']:raise StateError('Saved replica changed; no overwrite performed')
    pointer={'path':str(target.resolve()),'envelope':{k:v for k,v in envelope.items() if k!='snapshot'},
        'verified_at':utcnow().isoformat(),'manifest':envelope['snapshot']['manifest']}
    fd,tmp=tempfile.mkstemp(prefix='head-',dir=directory)
    with os.fdopen(fd,'w') as stream:json.dump(pointer,stream,allow_nan=False)
    os.replace(tmp,directory/'head.json')
    return pointer


def saved_replica(directory):
    """No remote access. Fail closed if a pointer does not match pristine bytes."""
    directory=Path(directory).resolve()
    try:
        p=json.loads((directory/'head.json').read_text());path=Path(p['path']).resolve()
        if path.parent!=directory or sha256(path.read_bytes()).hexdigest()!=p['manifest']['sha256']:raise StateError('Saved shared replica integrity failed')
        return p
    except FileNotFoundError:return None


def open_replica(directory,fallback,config=None):
    """Read-side local working copy. It never commits to the remote writer head."""
    from intelligence.storage import Store
    p=saved_replica(directory)
    if p:
        # SQLite application diagnostics may write locally; never modify pristine
        # verified bytes or present those writes as authoritative publications.
        path=Path(directory)/('view-'+str(p['envelope']['generation'])+'.sqlite3')
        if not path.exists():
            with open(p['path'],'rb') as source,os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as dest:dest.write(source.read())
        store=Store(path,read_replica=True);hydrate_budgets(store,p['envelope'])
        store.shared_status={k:v for k,v in p.items() if k!='path'}
    else:
        store=Store(fallback,read_replica=True);store.shared_status={'problem':'No saved shared replica. Use the explicit state sync after bootstrap; no sports requests will occur.'}
    return store
