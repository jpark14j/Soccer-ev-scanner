-- Run ONLY in a user-created Supabase project for the development preview.
-- No schedules, accounts, sports requests or billing settings are activated.
-- SQLite has one fenced writer; Postgres owns budgets BEFORE external I/O.
BEGIN;
CREATE TABLE IF NOT EXISTS public.research_control_state (
  id boolean PRIMARY KEY DEFAULT true CHECK (id), generation bigint NOT NULL DEFAULT 0,
  fence bigint NOT NULL DEFAULT 0, owner text, lease_until timestamptz,
  reader_hash text NOT NULL DEFAULT '', held boolean NOT NULL DEFAULT true,
  heartbeat jsonb NOT NULL DEFAULT '{}', updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.research_control_state(id) VALUES(true) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS public.research_state_snapshots (
  generation bigint PRIMARY KEY, at timestamptz NOT NULL, manifest jsonb NOT NULL,
  compressed text NOT NULL CHECK(length(compressed)<=6000000)
);
CREATE TABLE IF NOT EXISTS public.research_provider_budget (
  day date NOT NULL, provider text NOT NULL CHECK(provider IN ('odds','results','discovery')),
  used integer NOT NULL CHECK(used>=0), PRIMARY KEY(day,provider)
);
CREATE TABLE IF NOT EXISTS public.research_control_audit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, at timestamptz NOT NULL DEFAULT now(),
  action text NOT NULL, details jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS public.research_reservations (
  id text PRIMARY KEY, day date NOT NULL, provider text NOT NULL,
  reserved integer NOT NULL, actual integer, owner text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.research_completed_runs (
  id text PRIMARY KEY, at timestamptz NOT NULL, generation bigint NOT NULL
);
CREATE TABLE IF NOT EXISTS public.research_publication_receipts (
  id text PRIMARY KEY, at timestamptz NOT NULL, generation bigint NOT NULL, kickoff timestamptz NOT NULL
);
ALTER TABLE public.research_control_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_state_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_provider_budget ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_control_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_completed_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_publication_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.research_control_state, public.research_state_snapshots,
  public.research_provider_budget, public.research_control_audit, public.research_reservations,
  public.research_completed_runs, public.research_publication_receipts FROM anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.research_state_view() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT jsonb_build_object('generation',c.generation,'held',c.held,'heartbeat',c.heartbeat,
   'lease_until',c.lease_until,'server_at',now(),
   'snapshot',(SELECT to_jsonb(s) FROM public.research_state_snapshots s WHERE s.generation=c.generation),
   'budgets',COALESCE((SELECT jsonb_agg(to_jsonb(b)) FROM public.research_provider_budget b WHERE b.day >= (now() AT TIME ZONE 'UTC')::date-1),'[]'::jsonb),
   'publication_receipts',COALESCE((SELECT jsonb_agg(to_jsonb(p)) FROM public.research_publication_receipts p),'[]'::jsonb))
 FROM public.research_control_state c WHERE id;
$$;
REVOKE ALL ON FUNCTION public.research_state_view() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.research_state_view() TO service_role;

CREATE OR REPLACE FUNCTION public.research_state_read(p_token text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF length(p_token)<32 OR length(p_token)>256 OR NOT EXISTS (
   SELECT 1 FROM public.research_control_state WHERE id AND reader_hash<>''
     AND reader_hash=encode(sha256(convert_to(p_token,'UTF8')),'hex')) THEN
   RAISE EXCEPTION 'Research reader not configured';
 END IF;
 RETURN public.research_state_view();
END; $$;
REVOKE ALL ON FUNCTION public.research_state_read(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.research_state_read(text) TO anon,authenticated,service_role;

CREATE OR REPLACE FUNCTION public.research_control(p_action text,p_owner text,p_fence bigint,p_data jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE c public.research_control_state; t timestamptz:=clock_timestamp();
 d date:=(t AT TIME ZONE 'UTC')::date; kind text; amount integer; cap integer;
 used_n integer; rid text; gen bigint; item jsonb; stamp integer;
BEGIN
 SELECT * INTO c FROM public.research_control_state WHERE id FOR UPDATE;
 t:=clock_timestamp();d:=(t AT TIME ZONE 'UTC')::date;
 IF p_owner IS NULL OR p_owner !~ '^[a-f0-9]{32}$' THEN RAISE EXCEPTION 'Invalid writer identity'; END IF;
 IF p_action='acquire' THEN
   IF p_data->>'run_id' IS NULL OR p_data->>'run_id' !~ '^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'Invalid run identity'; END IF;
   IF EXISTS(SELECT 1 FROM public.research_completed_runs WHERE id=p_data->>'run_id') THEN
     RETURN jsonb_build_object('ok',false,'code','duplicate_run'); END IF;
   IF c.owner IS NOT NULL AND c.lease_until>t THEN
     RETURN jsonb_build_object('ok',false,'code','writer_busy'); END IF;
   UPDATE public.research_control_state SET owner=p_owner,fence=fence+1,lease_until=t+interval '15 minutes',
     heartbeat=jsonb_build_object('status','running','started_at',t,'run_id',p_data->>'run_id',
       'last_success_at',c.heartbeat->'last_success_at','last_error_code',c.heartbeat->'last_error_code') WHERE id;
   INSERT INTO public.research_control_audit(action,details) VALUES('acquire',jsonb_build_object('run_id',p_data->>'run_id','fence',c.fence+1));
   RETURN public.research_state_view() || jsonb_build_object('ok',true,'fence',c.fence+1);
 END IF;
 IF c.owner IS DISTINCT FROM p_owner OR c.fence IS DISTINCT FROM p_fence OR c.lease_until IS NULL OR c.lease_until<=t THEN
   RETURN jsonb_build_object('ok',false,'code','lease_lost'); END IF;
 IF p_action='reserve' THEN
   kind:=p_data->>'provider'; amount:=(p_data->>'cost')::integer; rid:=p_data->>'id';
   cap:=CASE kind WHEN 'odds' THEN 9 WHEN 'results' THEN 6 WHEN 'discovery' THEN 12 ELSE 0 END;
   IF cap=0 OR amount<1 OR amount>cap OR rid !~ '^[a-f0-9]{32}$' THEN RAISE EXCEPTION 'Invalid reservation'; END IF;
   stamp:=extract(epoch FROM ((t AT TIME ZONE 'UTC')::time))::integer;
   IF c.held OR stamp<60 OR stamp>86339 THEN RETURN jsonb_build_object('ok',false,'code','budget_hold_or_day_boundary'); END IF;
   IF EXISTS(SELECT 1 FROM public.research_reservations WHERE id=rid) THEN
     RETURN jsonb_build_object('ok',false,'code','reservation_already_consumed'); END IF;
   INSERT INTO public.research_provider_budget VALUES(d,kind,0) ON CONFLICT DO NOTHING;
   SELECT used INTO used_n FROM public.research_provider_budget WHERE day=d AND provider=kind FOR UPDATE;
   IF used_n+amount>cap THEN RETURN jsonb_build_object('ok',false,'code','daily_budget'); END IF;
   UPDATE public.research_provider_budget SET used=used+amount WHERE day=d AND provider=kind;
   INSERT INTO public.research_reservations VALUES(rid,d,kind,amount,NULL,p_owner);
   RETURN jsonb_build_object('ok',true,'day',d,'used',used_n+amount,'id',rid);
 ELSIF p_action='charge' THEN
   rid:=p_data->>'id'; amount:=(p_data->>'actual')::integer;
   SELECT reserved,provider,day INTO used_n,kind,d FROM public.research_reservations WHERE id=rid AND owner=p_owner AND actual IS NULL FOR UPDATE;
   IF NOT FOUND THEN RETURN jsonb_build_object('ok',false,'code','unknown_or_reconciled_reservation'); END IF;
   IF amount<0 OR amount>10000 THEN RAISE EXCEPTION 'Invalid provider cost'; END IF;
   UPDATE public.research_reservations SET actual=amount WHERE id=rid;
   -- Never refund uncertain reservations. Unexpected provider billing halts I/O.
   IF amount>used_n OR (kind='discovery' AND amount>0) THEN
     IF kind='discovery' THEN
       INSERT INTO public.research_provider_budget VALUES(d,'odds',amount) ON CONFLICT(day,provider) DO UPDATE SET used=research_provider_budget.used+excluded.used;
     ELSE
       UPDATE public.research_provider_budget SET used=used+amount-used_n WHERE day=d AND provider=kind;
     END IF;
     UPDATE public.research_control_state SET held=true WHERE id;
     INSERT INTO public.research_control_audit(action,details) VALUES('unexpected_cost_hold',jsonb_build_object('reservation',rid,'actual',amount));
   END IF;
   RETURN jsonb_build_object('ok',amount<=used_n AND NOT(kind='discovery' AND amount>0),'code',CASE WHEN amount>used_n OR (kind='discovery' AND amount>0) THEN 'unexpected_cost_hold' ELSE 'reconciled' END);
 ELSIF p_action='cost_unknown' THEN
   UPDATE public.research_control_state SET held=true WHERE id;
   INSERT INTO public.research_control_audit(action,details) VALUES('unknown_cost_hold','{}');
   RETURN jsonb_build_object('ok',false,'code','unknown_cost_hold');
 ELSIF p_action='checkpoint' THEN
   gen:=(p_data->>'expected_generation')::bigint;
   IF gen IS DISTINCT FROM c.generation THEN RETURN jsonb_build_object('ok',false,'code','generation_conflict'); END IF;
   IF length(p_data->>'compressed')>6000000 OR p_data->'manifest'->>'compressed_sha256'<>
     encode(sha256(decode(p_data->>'compressed','base64')),'hex') THEN RAISE EXCEPTION 'Snapshot checksum/size'; END IF;
   IF c.generation>0 AND p_data->'manifest'->>'store_instance' IS DISTINCT FROM
      (SELECT manifest->>'store_instance' FROM public.research_state_snapshots WHERE generation=c.generation) THEN RAISE EXCEPTION 'Store identity changed'; END IF;
   IF p_data->>'prospective_deadline' IS NOT NULL AND (p_data->>'prospective_deadline')::timestamptz<=t THEN
      RETURN jsonb_build_object('ok',false,'code','missed_pregame_commit'); END IF;
   IF jsonb_array_length(COALESCE(p_data->'publications','[]'))>3 THEN RAISE EXCEPTION 'Publication bound'; END IF;
   FOR item IN SELECT * FROM jsonb_array_elements(COALESCE(p_data->'publications','[]')) LOOP
     IF (item->>'kickoff')::timestamptz<=t OR (item->>'prepared_at')::timestamptz>t THEN RAISE EXCEPTION 'Not pregame'; END IF;
     INSERT INTO public.research_publication_receipts VALUES(item->>'id',t,c.generation+1,(item->>'kickoff')::timestamptz) ON CONFLICT DO NOTHING;
   END LOOP;
   INSERT INTO public.research_state_snapshots VALUES(c.generation+1,t,p_data->'manifest',p_data->>'compressed');
   INSERT INTO public.research_completed_runs VALUES(p_data->>'run_id',t,c.generation+1);
   UPDATE public.research_control_state SET generation=c.generation+1,owner=NULL,lease_until=NULL,updated_at=t,
     heartbeat=jsonb_build_object('status','completed','last_success_at',t,'run_id',p_data->>'run_id',
       'summary',p_data->'summary','last_error_code',c.heartbeat->'last_error_code') WHERE id;
   INSERT INTO public.research_control_audit(action,details) VALUES('checkpoint',jsonb_build_object('generation',c.generation+1,'run_id',p_data->>'run_id','sha256',p_data->'manifest'->>'sha256'));
   DELETE FROM public.research_state_snapshots WHERE generation<c.generation;
   RETURN jsonb_build_object('ok',true,'generation',c.generation+1,'committed_at',t);
 ELSIF p_action='fail' THEN
   UPDATE public.research_control_state SET owner=NULL,lease_until=NULL,
     heartbeat=c.heartbeat || jsonb_build_object('status','failed','last_error_at',t,'last_error_code','worker_failed') WHERE id;
   INSERT INTO public.research_control_audit(action,details) VALUES('worker_failed',jsonb_build_object('fence',p_fence));
   RETURN jsonb_build_object('ok',true);
 END IF;
 RAISE EXCEPTION 'Unsupported research action';
END; $$;
REVOKE ALL ON FUNCTION public.research_control(text,text,bigint,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.research_control(text,text,bigint,jsonb) TO service_role;
COMMIT;
-- Deliberately held and reader unconfigured. See docs/PHASE10_OPERATIONS.md.
