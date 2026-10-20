"""Owner-only GitHub dispatch control. Never calls a sports API or writes state.

The separate private workflow is the sole writer and rechecks every permission,
remote hold and budget. HTTP failures are never retried after a dispatch attempt.
"""
from dataclasses import dataclass,field
from datetime import timedelta
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from uuid import uuid4
import base64,json,os,re,subprocess
import requests
from intelligence.domain import utcnow,parse_time

REPOSITORY='jpark14j/sports-ai-private-recovery'
WORKFLOW='development_research.yml'
IDENTITY='478dbf23ce374b0dafc727eca737bc5e'
API='https://api.github.com/repos/'+REPOSITORY
MAX_RESPONSE=256*1024


class ManualError(ValueError):
    """Only constant, non-secret messages may be supplied."""


@dataclass(frozen=True)
class Config:
    enabled:bool=False
    github_token:str=field(default='',repr=False)
    owner_hash:str=field(default='',repr=False)
    app_commit:str=''

    @property
    def problem(self):
        if not self.enabled:return 'On-demand research is paused pending owner setup and data-use review.'
        if not re.fullmatch('github_pat_[A-Za-z0-9_]{20,255}',self.github_token):return 'Private on-demand access is not configured.'
        if not re.fullmatch('[a-f0-9]{64}',self.owner_hash):return 'Private owner authentication is not configured.'
        if not re.fullmatch('[a-f0-9]{40}',self.app_commit):return 'The deployed application revision could not be verified.'
        return None


def deployed_commit():
    try:
        value=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parent.parent,
            stderr=subprocess.DEVNULL,timeout=2,text=True).strip()
        return value if re.fullmatch('[a-f0-9]{40}',value) else ''
    except (OSError,subprocess.SubprocessError):return ''


def configuration(getter=None):
    def get(name):
        value=os.getenv(name)
        if value is None and getter:value=getter(name)
        return str(value or '')
    return Config(get('RESEARCH_MANUAL_ENABLED')=='1',get('RESEARCH_MANUAL_GITHUB_TOKEN'),
        get('RESEARCH_MANUAL_OWNER_HASH'),get('RESEARCH_MANUAL_APP_COMMIT') or deployed_commit())


def auth_scope(config):return sha256((config.owner_hash+'|'+config.github_token).encode()).hexdigest()


def unlock(state,code,config,now=None):
    now=now or utcnow();state.pop('authorized_until',None);state.pop('auth_scope',None)
    # Require a randomly generated 256-bit code, not a user-chosen password.
    valid=isinstance(code,str) and bool(re.fullmatch('[a-f0-9]{64}',code))
    if not valid or not re.fullmatch('[a-f0-9]{64}',config.owner_hash):return False
    if not compare_digest(sha256(code.encode()).hexdigest(),config.owner_hash):return False
    state.update(authorized_until=(now+timedelta(minutes=10)).isoformat(),auth_scope=auth_scope(config))
    return True


def authorized(state,config,now=None):
    try:return (state.get('auth_scope')==auth_scope(config)
        and 0<(parse_time(state['authorized_until'])-(now or utcnow())).total_seconds()<=600)
    except (KeyError,TypeError,ValueError):return False


def preflight(config,state,store,now=None):
    now=now or utcnow()
    if config.problem:return config.problem
    if not authorized(state,config,now):return 'Unlock private research access before requesting new data.'
    p=getattr(store,'shared_status',{});e=p.get('envelope',{})
    if not getattr(store,'read_replica',False):return 'On-demand research requires the verified shared read-only view.'
    if p.get('manifest',{}).get('store_instance')!=IDENTITY or type(e.get('generation')) is not int or e['generation']<1:
        return 'The saved research store identity is not verified.'
    try:fresh=0<=(now-parse_time(p['verified_at'])).total_seconds()<=300
    except (KeyError,TypeError,ValueError):fresh=False
    if not fresh:return 'Refresh the saved view before requesting research. No provider requests were made.'
    if e.get('held') is not False:return 'Research is paused by the provider usage hold. Owner review is required; this button cannot release it.'
    from intelligence.quota import quota_details
    q=quota_details(store,9,now)
    if q['recovery_hold'] or q['local_remaining']<1:return 'The saved research allowance is unavailable. No limits or holds were changed.'
    pending=state.get('pending')
    if pending and pending.get('phase') not in ('failed','synced'):
        return 'A research request is already awaiting confirmation. Check its status before requesting again.'
    last=state.get('attempted_at')
    try:
        if last and (now-parse_time(last)).total_seconds()<300:return 'Wait five minutes between research requests; existing results remain available.'
    except (ValueError,TypeError):return 'Saved request timing is unavailable. Inspect private request status before trying again.'
    return None


class DispatchClient:
    def __init__(self,config,session=None):
        self.config=config;self.session=session or requests.Session()

    def _http(self,method,path,payload=None):
        # Every URL/operation is selected by this module, never by chat/user input.
        headers={'Authorization':'Bearer '+self.config.github_token,'Accept':'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28'}
        try:
            response=self.session.request(method,API+path,headers=headers,json=payload,
                timeout=(5,20),allow_redirects=False,stream=True)
            try:
                if response.status_code not in (200,204):raise ManualError('Private research access failed. The owner must check worker permissions and configuration.')
                if response.status_code==204:return {}
                raw=bytearray()
                for chunk in response.iter_content(8192):
                    raw.extend(chunk)
                    if len(raw)>MAX_RESPONSE:raise ManualError('Private research returned an oversized response.')
                value=json.loads(raw)
                if not isinstance(value,dict):raise ValueError()
                return value
            finally:response.close()
        except ManualError:raise
        except (requests.RequestException,ValueError,TypeError):
            raise ManualError('Research status could not be confirmed. No automatic dispatch retry was made.') from None

    def dispatch(self,request_id):
        if not re.fullmatch('[a-f0-9]{32}',request_id):raise ManualError('Invalid manual request identity.')
        repo=self._http('GET','')
        if repo.get('private') is not True:raise ManualError('The worker repository must remain private.')
        workflow=self._http('GET','/contents/.github/workflows/'+WORKFLOW+'?ref=main')
        try:
            if workflow.get('encoding')!='base64':raise ValueError()
            source=base64.b64decode(workflow['content'],validate=False).decode()
            # The installed private workflow has a reviewed literal pin.
            pins=re.findall(r'RESEARCH_APP_COMMIT: ([a-f0-9]{40})\s*\n',source)
            if pins!=[self.config.app_commit] or re.search(r'(?m)^\s*schedule\s*:',source):raise ValueError()
        except (ValueError,KeyError,UnicodeError):
            raise ManualError('The private worker revision or manual-only configuration needs owner review.') from None
        self._http('POST','/actions/workflows/'+WORKFLOW+'/dispatches',{
            'ref':'main','inputs':{'operation':'manual-research','request_id':request_id,'expected_app_commit':self.config.app_commit}})

    def status(self,request_id):
        if not re.fullmatch('[a-f0-9]{32}',request_id):raise ManualError('Saved research request is invalid.')
        data=self._http('GET','/actions/workflows/'+WORKFLOW+'/runs?event=workflow_dispatch&branch=main&per_page=20')
        matches=[r for r in data.get('workflow_runs',[]) if r.get('display_title')=='Manual research '+request_id
            and r.get('event')=='workflow_dispatch' and r.get('head_branch')=='main']
        if len(matches)>1:raise ManualError('Multiple matching research runs require owner review; no new request was sent.')
        if not matches:return {'phase':'unconfirmed'}
        run=matches[0]
        return {'phase':'failed' if run.get('status')=='completed' and run.get('conclusion')!='success'
            else 'awaiting_saved_results' if run.get('status')=='completed' else 'running'}


def request_research(config,state,store,now=None,client=None):
    now=now or utcnow();problem=preflight(config,state,store,now)
    if problem:raise ManualError(problem)
    request_id=uuid4().hex
    state.update(attempted_at=now.isoformat(),pending={'id':request_id,'phase':'unconfirmed',
        'at':now.isoformat(),'baseline_generation':store.shared_status['envelope']['generation']})
    # Pending is saved before any HTTP. Ambiguous dispatches must be reconciled,
    # never blindly retried (including after a connection failure).
    (client or DispatchClient(config)).dispatch(request_id)
    state['pending']['phase']='queued'
    return request_id


def poll(config,state,store,now=None,client=None):
    now=now or utcnow()
    if config.problem or not authorized(state,config,now):raise ManualError('Unlock private access to check this request.')
    pending=state.get('pending')
    if not pending:return None
    e=getattr(store,'shared_status',{}).get('envelope',{});summary=e.get('heartbeat',{}).get('summary',{})
    if (e.get('generation',0)>pending['baseline_generation'] and summary.get('manual_request_id')==pending['id']):
        pending['phase']='synced';return pending['phase']
    last=state.get('polled_at')
    if last and (now-parse_time(last)).total_seconds()<30:return pending['phase']
    state['polled_at']=now.isoformat()
    pending.update((client or DispatchClient(config)).status(pending['id']))
    return pending['phase']
