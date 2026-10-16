"""Versioned research artifacts, drift diagnostics and reviewed promotion gates.

Training never activates a model. A registry approval is additionally required by
the publication pipeline. Unseen-period/licensing evidence cannot be inferred.
"""
from collections import defaultdict
import json
from intelligence.domain import digest,parse_time,utcnow
from intelligence.evaluation import promotion_reasons,evaluate_history

POLICY={'minimum_forward_decisions':100,'minimum_unseen_test':200,'maximum_calibration_gap':.05,
        'paired_improvement_lower_required':0.,'drift_window':100,'brier_review_increase':.03}


def ensure_registry(store):
    with store.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS model_artifacts(id TEXT PRIMARY KEY,at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS model_actions(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,artifact_id TEXT NOT NULL,action TEXT NOT NULL,review_reference TEXT NOT NULL,evidence TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS artifact_no_update BEFORE UPDATE ON model_artifacts BEGIN SELECT RAISE(ABORT,'Immutable model artifact'); END;
        CREATE TRIGGER IF NOT EXISTS artifact_no_delete BEFORE DELETE ON model_artifacts BEGIN SELECT RAISE(ABORT,'Immutable model artifact'); END;
        CREATE TRIGGER IF NOT EXISTS model_action_no_update BEFORE UPDATE ON model_actions BEGIN SELECT RAISE(ABORT,'Immutable model action'); END;
        CREATE TRIGGER IF NOT EXISTS model_action_no_delete BEFORE DELETE ON model_actions BEGIN SELECT RAISE(ABORT,'Immutable model action'); END;
        ''')


def register_artifact(store,report,folds=()):
    ensure_registry(store)
    if report.get('evidence_id')!=digest({k:v for k,v in report.items() if k!='evidence_id'}):
        raise ValueError('Evaluation content hash is invalid')
    payload={'report':report,'walk_forward_folds':list(folds),'policy':POLICY,
             'status':'candidate; not activated','code_sha256':report.get('code_sha256'),
             'data_sha256':report.get('data_sha256')}
    identifier=digest(payload)
    with store.connect() as db:
        db.execute('INSERT OR IGNORE INTO model_artifacts VALUES(?,?,?)',
                   (identifier,utcnow().isoformat(),json.dumps(payload,allow_nan=False)))
    return identifier


def train_challenger(history,sport,league,source,store):
    """Expanding date folds; reports stay exploratory unless fresh evidence exists."""
    if len(history)<1000:
        raise ValueError('At least 1,000 provenance-checked games required for expanding folds')
    days=sorted(history.date.unique());reports=[]
    for fraction in (.7,.85,1.):
        cutoff=days[min(len(days)-1,int(len(days)*fraction)-1)]
        subset=history[history.date<=cutoff]
        report=evaluate_history(subset,sport,league,source)
        reports.append(report)
    identifier=register_artifact(store,reports[-1],[{'data_end':r['data_end'],'test_start':r['test_start'],
        'test_n':r['test_n'],'metrics':r['metrics'],'evidence_id':r['evidence_id']} for r in reports])
    champion=active_champion(store,sport,'h2h')
    comparison=compare_challenger(reports[-1],champion)
    return {'artifact_id':identifier,'folds':len(reports),'champion_comparison':comparison,
        'fold_note':'Expanding windows can overlap; these are not independent confirmation trials',
        'status':'candidate only; promotion disabled without reviewed unseen-period evidence'}


def compare_challenger(candidate,champion):
    if not champion:
        return {'status':'No active reviewed champion; no performance difference asserted'}
    fields=('sport','league','market','data_sha256','test_start','test_n')
    if any(candidate.get(k)!=champion.get(k) for k in fields):
        return {'status':'Incomparable evaluation data/period; re-evaluate on a common fresh locked period'}
    return {'status':'Same evaluation target/period; diagnostic differences only, not promotion evidence',
        'brier_change':candidate['metrics']['brier']-champion['metrics']['brier'],
        'log_loss_change':candidate['metrics']['log_loss']-champion['metrics']['log_loss']}


def promotion_blockers(report,evidence,now=None):
    now=now or utcnow();reasons=list(promotion_reasons(report))
    requirements={'fresh_unseen_period_verified':'Fresh independent unseen-period validation is unverified',
        'commercial_data_rights_verified':'Permitted model/data usage is unverified',
        'operator_scope_verified':'Operator market/settlement scope is unverified'}
    reasons.extend(reason for key,reason in requirements.items() if evidence.get(key) is not True)
    if evidence.get('forward_decisions',0)<POLICY['minimum_forward_decisions']:
        reasons.append('At least 100 unique forward decisions required')
    if evidence.get('paired_improvement_lower',-1)<=0:
        reasons.append('Positive dependence-aware held-out improvement lower bound is missing')
    if not evidence.get('verification_source','').startswith('https://'):
        reasons.append('Independent verification reference is missing')
    try:
        if not parse_time(report['generated_at'])<=now<=parse_time(report['expires_at']):
            reasons.append('Model report is expired or future-dated')
    except (KeyError,ValueError):
        reasons.append('Model report validity times are missing')
    return list(dict.fromkeys(reasons))


def change_champion(store,artifact_id,evidence,review_reference,action='promote',now=None):
    ensure_registry(store);now=now or utcnow()
    if action not in ('promote','rollback') or not review_reference.startswith('https://'):
        raise ValueError('Explicit reviewed promotion/rollback reference required')
    with store.connect() as db:
        row=db.execute('SELECT payload FROM model_artifacts WHERE id=?',(artifact_id,)).fetchone()
        if not row:
            raise ValueError('Unknown model artifact')
        report=json.loads(row['payload'])['report']
        if action=='rollback' and not db.execute("SELECT 1 FROM model_actions WHERE artifact_id=? AND action='promote'",(artifact_id,)).fetchone():
            raise ValueError('Rollback requires a previously approved artifact')
        blockers=promotion_blockers(report,evidence,now)
        if blockers:
            raise ValueError('Model activation blocked: '+'; '.join(blockers))
        db.execute('INSERT INTO model_actions(at,artifact_id,action,review_reference,evidence) VALUES(?,?,?,?,?)',
            (now.isoformat(),artifact_id,action,review_reference,json.dumps(evidence,allow_nan=False)))


def active_champion(store,sport,market):
    ensure_registry(store)
    with store.connect() as db:
        rows=db.execute('SELECT a.payload FROM model_actions m JOIN model_artifacts a ON a.id=m.artifact_id ORDER BY m.id DESC').fetchall()
    for row in rows:
        report=json.loads(row['payload'])['report']
        if (report.get('sport'),report.get('market'))==(sport,market):
            return report
    return None


def drift_report(records):
    groups=defaultdict(dict)
    for record in records:
        if record.get('outcome') not in ('win','loss'):
            continue
        q,e=record['payload']['quote'],record['payload']['estimate']
        key=(q['sport'],q['market'],e['model_version'])
        # Avoid treating multiple same-event selections as independent decisions.
        groups[key].setdefault((q['provider'],q['event_id']),record)
    result=[];n=POLICY['drift_window']
    for key,unique in sorted(groups.items()):
        rows=sorted(unique.values(),key=lambda r:parse_time(r.get('settled_at') or r['at']))
        item={'sport':key[0],'market':key[1],'model':key[2],'unique_settled_events':len(rows),
              'status':'insufficient data','automatic_action':'none'}
        if len(rows)>=2*n:
            def brier(batch):
                return sum((r['payload']['estimate']['probability']-int(r['outcome']=='win'))**2 for r in batch)/len(batch)
            previous,recent=brier(rows[-2*n:-n]),brier(rows[-n:])
            item.update(previous_brier=previous,recent_brier=recent,
                status='review model drift' if recent-previous>POLICY['brier_review_increase'] else 'no threshold alert',
                limitation='Predefined diagnostic threshold, not a formal change-point test; time dependence and selection effects remain')
        result.append(item)
    return result


def registry_status(store):
    ensure_registry(store)
    with store.connect() as db:
        artifacts=db.execute('SELECT count(*) FROM model_artifacts').fetchone()[0]
        actions=db.execute('SELECT count(*) FROM model_actions').fetchone()[0]
    return {'candidate_artifacts':artifacts,'reviewed_actions':actions,
        'scheduled_retraining':'Disabled: no independent scheduler/durable licensed current-history pipeline configured',
        'automatic_promotion':False,'policy':POLICY,'forward_drift':drift_report(store.records())}
