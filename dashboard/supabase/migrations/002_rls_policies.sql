-- =============================================================================
-- 002_rls_policies.sql
-- Row Level Security, role helpers and grants.
--
-- Access model (one data model, three audiences)
--   owner    -> every table and every view, all entities (incl. 13-week cash flow)
--   finance  -> granular tables + finance views, scoped by user_roles.entity_id
--               (null entity_id = all entities)
--   board    -> summary views only (v_board_kpis, v_cash_position,
--               v_ar_ap_aging_summary); zero rows from any base table
--
-- How "board can only read the views" works on Postgres 15+ / Supabase
--   1. Every base table has RLS enabled. The only SELECT policies are for
--      owner and finance. A board user therefore gets 0 rows from a table
--      even though SELECT is granted to `authenticated`.
--   2. The views in 003 are created with `security_invoker = false` (the
--      default) and are owned by the migration role (`postgres` on Supabase).
--      With security_invoker = false Postgres checks privileges and RLS as
--      the VIEW OWNER, and a table owner bypasses RLS unless FORCE ROW LEVEL
--      SECURITY is set (it is not). So the views see all rows.
--   3. Because the views bypass table RLS, each view filters itself with
--      app.can_view(entity_id, '{owner,board,...}') in its WHERE clause.
--      Those helpers are SECURITY DEFINER so they can read user_roles, and
--      they evaluate auth.uid() of the calling session (views do not change
--      the session user; only SECURITY DEFINER functions do).
--   4. Writes: no INSERT/UPDATE/DELETE policies exist for anon/authenticated,
--      and the privileges are revoked as well. The service role (n8n,
--      extract.py) bypasses RLS and is the only writer.
--   5. Non-JWT clients (Metabase, psql): a Postgres login role that is a
--      member of dash_owner / dash_finance / dash_board is mapped to that
--      audience by app.current_role(). That is how a read-only Metabase
--      role sees finance-level data without a Supabase JWT.
--
-- Do NOT set FORCE ROW LEVEL SECURITY on these tables or (2) stops working.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Audience group roles for non-JWT database logins (Metabase, analysts)
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'dash_owner') then
    create role dash_owner nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'dash_finance') then
    create role dash_finance nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'dash_board') then
    create role dash_board nologin;
  end if;
end
$$;

comment on role dash_owner   is 'Group role: DB logins that should be treated as the owner audience by app.current_role().';
comment on role dash_finance is 'Group role: DB logins treated as finance (all entities).';
comment on role dash_board   is 'Group role: DB logins treated as board (summary views only).';

-- ---------------------------------------------------------------------------
-- Helper functions (schema app)
-- SECURITY DEFINER + empty search_path per Supabase guidance; everything is
-- schema-qualified. STABLE so the planner caches the result within a query.
-- ---------------------------------------------------------------------------

-- Resolve the audience of the current session.
-- Priority when a user holds several rows: owner > finance > board.
create or replace function app.current_role()
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(
    -- 1) Supabase JWT user
    (select r.role
       from public.user_roles r
      where r.user_id = auth.uid()
      order by case r.role when 'owner' then 1 when 'finance' then 2 else 3 end
      limit 1),
    -- 2) Direct DB login mapped through group roles (Metabase etc.).
    --    session_user, not current_user: inside a SECURITY DEFINER function
    --    current_user is the function owner. For PostgREST sessions
    --    session_user is 'authenticator', which is in no dash_* role, so the
    --    JWT branch above is the only one that can match.
    case
      when pg_catalog.pg_has_role(session_user, 'dash_owner',   'usage') then 'owner'
      when pg_catalog.pg_has_role(session_user, 'dash_finance', 'usage') then 'finance'
      when pg_catalog.pg_has_role(session_user, 'dash_board',   'usage') then 'board'
    end
  );
$$;
comment on function app.current_role() is 'Audience of the calling session: owner | finance | board | null. JWT user_roles first, then dash_* group-role membership.';

-- Can the current session see rows for this entity?
-- owner/board: all entities. finance: entity_id null row (all) or matching row.
create or replace function app.can_access_entity(p_entity_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select case app.current_role()
    when 'owner' then true
    when 'board' then true
    when 'finance' then
      -- JWT finance user: check their entity scope
      (auth.uid() is not null and exists (
         select 1 from public.user_roles r
          where r.user_id = auth.uid()
            and r.role = 'finance'
            and (r.entity_id is null or r.entity_id = p_entity_id)))
      -- DB-login finance (dash_finance): all entities
      or (auth.uid() is null and pg_catalog.pg_has_role(session_user, 'dash_finance', 'usage'))
    else false
  end;
$$;
comment on function app.can_access_entity(uuid) is 'Entity scoping: true for owner/board; finance only for entities in their user_roles scope (null = all).';

-- Combined check used by table policies and by every view:
-- audience must be in the allowed list AND entity must be in scope.
create or replace function app.can_view(p_entity_id uuid, p_audiences text[])
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select app.current_role() = any (p_audiences)
     and app.can_access_entity(p_entity_id);
$$;
comment on function app.can_view(uuid, text[]) is 'True when the session audience is one of p_audiences and may see p_entity_id. Views declare their audiences with this.';

-- Lock the helpers down: only the roles that need them may execute.
revoke all on function app.current_role()                from public;
revoke all on function app.can_access_entity(uuid)       from public;
revoke all on function app.can_view(uuid, text[])        from public;
revoke all on function app.set_updated_at()              from public;

grant usage on schema app to authenticated, service_role, dash_owner, dash_finance, dash_board;
grant execute on function app.current_role()          to authenticated, service_role, dash_owner, dash_finance, dash_board;
grant execute on function app.can_access_entity(uuid) to authenticated, service_role, dash_owner, dash_finance, dash_board;
grant execute on function app.can_view(uuid, text[])  to authenticated, service_role, dash_owner, dash_finance, dash_board;

-- ---------------------------------------------------------------------------
-- Table privileges: anon gets nothing; authenticated gets SELECT only
-- (rows filtered by RLS); service_role keeps full access for ingestion.
-- Supabase's default privileges grant ALL on new public tables to
-- anon/authenticated, so revoke explicitly.
-- ---------------------------------------------------------------------------
revoke all on all tables in schema public from anon;
revoke all on all tables in schema public from authenticated;

grant select on
  public.entities, public.fiscal_periods, public.chart_of_accounts, public.gl_balances,
  public.ar_aging, public.ap_aging, public.bank_balances, public.budgets,
  public.cashflow_forecast, public.ingestion_runs, public.user_roles
to authenticated;

grant all on all tables in schema public to service_role;

-- ---------------------------------------------------------------------------
-- Enable RLS on every table
-- ---------------------------------------------------------------------------
alter table public.entities          enable row level security;
alter table public.fiscal_periods    enable row level security;
alter table public.chart_of_accounts enable row level security;
alter table public.gl_balances       enable row level security;
alter table public.ar_aging          enable row level security;
alter table public.ap_aging          enable row level security;
alter table public.bank_balances     enable row level security;
alter table public.budgets           enable row level security;
alter table public.cashflow_forecast enable row level security;
alter table public.ingestion_runs    enable row level security;
alter table public.user_roles        enable row level security;

-- ---------------------------------------------------------------------------
-- SELECT policies. Granular tables: owner + finance (entity-scoped).
-- No board policy on tables by design. No write policies at all.
-- ---------------------------------------------------------------------------
create policy entities_select_owner_finance on public.entities
  for select to authenticated
  using (app.can_view(id, array['owner', 'finance']));

create policy fiscal_periods_select_owner_finance on public.fiscal_periods
  for select to authenticated
  using (app.can_view(entity_id, array['owner', 'finance']));

create policy chart_of_accounts_select_owner_finance on public.chart_of_accounts
  for select to authenticated
  using (app.can_view(entity_id, array['owner', 'finance']));

create policy gl_balances_select_owner_finance on public.gl_balances
  for select to authenticated
  using (app.can_view(entity_id, array['owner', 'finance']));

create policy ar_aging_select_owner_finance on public.ar_aging
  for select to authenticated
  using (app.can_view(entity_id, array['owner', 'finance']));

create policy ap_aging_select_owner_finance on public.ap_aging
  for select to authenticated
  using (app.can_view(entity_id, array['owner', 'finance']));

create policy bank_balances_select_owner_finance on public.bank_balances
  for select to authenticated
  using (app.can_view(entity_id, array['owner', 'finance']));

create policy budgets_select_owner_finance on public.budgets
  for select to authenticated
  using (app.can_view(entity_id, array['owner', 'finance']));

-- 13-week cash flow is owner-only at table level (finance sees it through
-- v_cashflow_13w only if you widen the audience list there).
create policy cashflow_forecast_select_owner on public.cashflow_forecast
  for select to authenticated
  using (app.can_view(entity_id, array['owner']));

-- Ingestion audit: owner sees all; finance sees runs for their entities and
-- group-wide runs (entity_id null).
create policy ingestion_runs_select_owner_finance on public.ingestion_runs
  for select to authenticated
  using (
    app.current_role() = 'owner'
    or (app.current_role() = 'finance'
        and (entity_id is null or app.can_access_entity(entity_id)))
  );

-- user_roles: a user may read their own grants; owner may read everyone's.
create policy user_roles_select_self_or_owner on public.user_roles
  for select to authenticated
  using (user_id = auth.uid() or app.current_role() = 'owner');

-- Intentionally no INSERT/UPDATE/DELETE policies: with RLS enabled and no
-- policy, writes from anon/authenticated are rejected even before the
-- revoked privileges are considered. The service role bypasses RLS.
