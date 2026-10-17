"""Optional manual private Supabase Storage snapshots; disabled by default.

No request occurs on configuration/status/import. Credentials never enter
snapshots, receipts or error strings. A backup is not a shared primary database.
"""
from dataclasses import dataclass,field
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import json,os,re,sqlite3,tempfile
from urllib.parse import urlsplit
import requests
from intelligence.domain import utcnow,digest
from intelligence.persistence import backup_store
from intelligence.data_adapters import ROOT

LIMIT=20*1024*1024
OBJECT=re.compile(r'snapshots/[a-f0-9]{32}/[0-9]{8}T[0-9]{6}Z-[a-f0-9]{64}\.sqlite3')


class BackupError(ValueError):pass


@dataclass(frozen=True)
class Config:
    enabled:bool=False
    use_reviewed:bool=False
    url:str=''
    bucket:str='research-private'
    key:str=field(default='',repr=False)

    @property
    def problem(self):
        if not self.enabled:return 'Optional off-host backup is disabled'
        if not self.use_reviewed:return 'Free-tier, privacy and provider-use review required before backup activation'
        try:u=urlsplit(self.url)
        except ValueError:return 'Invalid backup project origin'
        if u.scheme!='https' or not re.fullmatch(r'[a-z0-9]{20}\.supabase\.co',u.netloc) or u.path not in ('','/') or u.query or u.fragment:
            return 'Only a configured official HTTPS Supabase project origin is supported'
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,62}',self.bucket):return 'Invalid private bucket name'
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}',self.key):
            return 'Configure the legacy server-only service_role JWT in Secrets; no key is requested in chat'
        return None


def configuration(getter=None):
    def get(name,default=''):
        value=os.getenv(name)
        if value is None and getter:value=getter(name)
        return default if value is None or value=='' else str(value)
    return Config(get('RESEARCH_REMOTE_BACKUP_ENABLED','0')=='1',get('RESEARCH_BACKUP_USE_REVIEWED','0')=='1',
        get('RESEARCH_BACKUP_URL'),get('RESEARCH_BACKUP_BUCKET','research-private'),get('RESEARCH_BACKUP_SERVICE_KEY'))


def status(store,config=None):
    c=config or configuration()
    with store.connect() as db:
        table=db.execute("SELECT 1 FROM sqlite_master WHERE name='remote_backup_receipts'").fetchone()
        row=db.execute('SELECT at,payload FROM remote_backup_receipts ORDER BY at DESC LIMIT 1').fetchone() if table else None
    return {'configured':c.problem is None,'problem':c.problem,'latest_receipt':json.loads(row['payload']) if row else None,
        'background_enabled':False,'shared_transactional_budgets':False,
        'note':'Manual private off-host snapshots only. No continuous durability, shared database, automatic recovery or scheduler is established by configuration.'}


def _check(c,name):
    if c.problem:raise BackupError(c.problem)
    if not OBJECT.fullmatch(name):raise BackupError('Invalid content-addressed backup reference')


def _download(c,name,session):
    _check(c,name)
    response=session.get(c.url.rstrip('/')+'/storage/v1/object/authenticated/'+c.bucket+'/'+name,
        headers={'apikey':c.key,'Authorization':'Bearer '+c.key},timeout=(5,20),allow_redirects=False,stream=True)
    try:
        if response.status_code!=200:raise BackupError('Private backup download failed; inspect provider access without sharing credentials')
        chunks=[];size=0
        for chunk in response.iter_content(65536):
            size+=len(chunk)
            if size>LIMIT:raise BackupError('Backup exceeds the 20 MiB application bound')
            chunks.append(chunk)
        raw=b''.join(chunks)
        expected=name.rsplit('-',1)[1][:-8]
        if sha256(raw).hexdigest()!=expected or not raw.startswith(b'SQLite format 3\x00'):raise BackupError('Downloaded backup checksum or SQLite format differs')
        return raw
    finally:response.close()


def _private(c,session):
    response=session.get(c.url.rstrip('/')+'/storage/v1/bucket/'+c.bucket,
        headers={'apikey':c.key,'Authorization':'Bearer '+c.key},timeout=(5,20),allow_redirects=False,stream=True)
    try:
        if response.status_code!=200:raise BackupError('Private bucket verification failed')
        chunks=[];size=0
        for chunk in response.iter_content(4096):
            size+=len(chunk)
            if size>16384:raise BackupError('Bucket metadata exceeds bound')
            chunks.append(chunk)
        data=json.loads(b''.join(chunks))
        if not isinstance(data,dict) or data.get('public') is not False or data.get('id')!=c.bucket:raise BackupError('Only an explicitly verified private bucket may receive or restore this database')
    finally:response.close()


def _assets(path):
    paths=['config/forward_research_policy.json','config/epl_forecast_policy.json','config/expanded_model_policy.json',
        'research_assets/epl/model.json','research_assets/expanded/soccer_de_bundesliga.json','research_assets/expanded/soccer_fr_ligue1.json',
        'research_assets/quantitative/evaluation.json','research_assets/quantitative/phase6.json','research_assets/quantitative/joint_validation.json']
    with closing(sqlite3.connect(path)) as db,db:
        # Asset writes must be checkpointed into the uploaded file, never left
        # in an unshipped WAL sidecar inherited from the source journal mode.
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('CREATE TABLE IF NOT EXISTS backup_model_assets(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,payload TEXT NOT NULL)')
        for name in paths:
            text=(ROOT/name).read_text()
            db.execute('INSERT OR REPLACE INTO backup_model_assets VALUES(?,?,?)',(name,sha256(text.encode()).hexdigest(),text))


def _valid(path):
    with closing(sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA trusted_schema=OFF');db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchone():raise BackupError('Backup database integrity failed')
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'store_identity','budget','cache','publications','settlements'}<=tables:raise BackupError('Required backup tables missing')


def upload(store,config=None,session=None,now=None):
    c=config or configuration();now=now or utcnow()
    if c.problem:raise BackupError(c.problem)
    owned=session is None;session=session or requests.Session()
    try:
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS remote_backup_attempts(day TEXT PRIMARY KEY,at TEXT NOT NULL)')
            if not db.execute('INSERT OR IGNORE INTO remote_backup_attempts VALUES(?,?)',(now.date().isoformat(),now.isoformat())).rowcount:
                raise BackupError('One manual off-host backup attempt per UTC day per store; no repeated upload')
        _private(c,session)
        with tempfile.TemporaryDirectory(prefix='private-backup-',dir=Path(store.path).resolve().parent) as folder:
            path=Path(folder)/'snapshot.sqlite3';backup_store(store,path);_assets(path);_valid(path)
            if path.stat().st_size>LIMIT:raise BackupError('Backup exceeds 20 MiB; no upload attempted')
            raw=path.read_bytes();checksum=sha256(raw).hexdigest()
            with closing(sqlite3.connect(path)) as db:instance=db.execute('SELECT instance FROM store_identity WHERE id=1').fetchone()[0]
            name='snapshots/'+instance+'/'+now.strftime('%Y%m%dT%H%M%SZ')+'-'+checksum+'.sqlite3';_check(c,name)
            response=session.post(c.url.rstrip('/')+'/storage/v1/object/'+c.bucket+'/'+name,
                data=raw,headers={'apikey':c.key,'Authorization':'Bearer '+c.key,'Content-Type':'application/octet-stream','x-upsert':'false'},
                timeout=(5,20),allow_redirects=False)
            try:
                if response.status_code not in (200,201,409):raise BackupError('Private backup upload failed; no durability inferred')
            finally:response.close()
            downloaded=_download(c,name,session)
            if downloaded!=raw:raise BackupError('Off-host readback differs')
            receipt={'at':now.isoformat(),'object_reference':name,'sha256':checksum,'bytes':len(raw),'store_instance':instance,
                'off_host_byte_roundtrip_verified':True,'continuous_durability_verified':False,
                'restore_into_active_store_performed':False,'provider_requests':3}
            with store.connect() as db:
                db.executescript('''
                CREATE TABLE IF NOT EXISTS remote_backup_receipts(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS remote_receipt_no_update BEFORE UPDATE ON remote_backup_receipts BEGIN SELECT RAISE(ABORT,'Immutable backup receipt'); END;
                CREATE TRIGGER IF NOT EXISTS remote_receipt_no_delete BEFORE DELETE ON remote_backup_receipts BEGIN SELECT RAISE(ABORT,'Immutable backup receipt'); END;
                ''')
                db.execute('INSERT OR IGNORE INTO remote_backup_receipts VALUES(?,?,?)',(digest(receipt),now.isoformat(),json.dumps(receipt)))
            return receipt
    except BackupError:raise
    except (requests.RequestException,sqlite3.Error,OSError,ValueError,TypeError):raise BackupError('Backup transport/storage failed; no durability inferred and no credential details logged') from None
    finally:
        if owned:session.close()


def restore(name,target,config=None,session=None):
    c=config or configuration();_check(c,name);target=Path(target)
    if target.exists():raise BackupError('Restore requires a new private file; existing/active databases are never replaced')
    target.parent.mkdir(parents=True,exist_ok=True);owned=session is None;session=session or requests.Session();created=False
    try:
        _private(c,session)
        raw=_download(c,name,session)
        with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:created=True;stream.write(raw)
        _valid(target)
        from intelligence.request_guard import hold
        with closing(sqlite3.connect(target)) as db,db:hold(db,'Restored off-host object '+name)
        return {'restored_to_new_file':True,'checksum_verified_before_recovery_hold':True,'provider_requests':2,
            'requests_blocked_until_review':True,'active_database_changed':False,
            'note':'Inspect records and reconcile provider usage before a deliberate reviewed migration. No automatic app switch.'}
    except BackupError:
        if created:target.unlink(missing_ok=True)
        raise
    except (requests.RequestException,sqlite3.Error,OSError,ValueError):
        if created:target.unlink(missing_ok=True)
        raise BackupError('Backup restore failed safely; no active database changed') from None
    finally:
        if owned:session.close()
