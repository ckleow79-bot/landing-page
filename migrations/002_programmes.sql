-- Programmes (seminars / workshops / courses) and registrations
-- Public site reads `programmes` where published = true; anyone may insert a registration.
-- Admin edits happen in the Supabase dashboard (Table Editor) or via an authenticated role.

create table if not exists programmes (
  id uuid default gen_random_uuid() primary key,
  slug text not null unique,
  title text not null,
  subtitle text,
  provider text not null check (provider in ('bk-training','high-impact','bk-academy','external')),
  organiser text,                    -- shown when provider = 'external'
  category text not null,
  format text,                       -- Seminar | Workshop | Webinar | Course
  mode text,                         -- In-person | Online | Hybrid
  venue text,
  start_date timestamptz not null,
  end_date timestamptz,
  cpd_hours numeric(5,1),
  hrdc_claimable boolean default false,
  language text,
  fee_myr numeric(10,2),
  early_bird_fee_myr numeric(10,2),
  early_bird_until date,
  status text not null default 'upcoming' check (status in ('upcoming','full','past','cancelled')),
  featured boolean default false,
  highlights jsonb default '[]'::jsonb,
  register_url text,
  brochure_url text,
  published boolean default true,
  created_at timestamptz default timezone('utc', now()),
  updated_at timestamptz default timezone('utc', now())
);

create index if not exists idx_programmes_start on programmes(start_date);
create index if not exists idx_programmes_published on programmes(published, status);

alter table programmes enable row level security;

create policy "Public can read published programmes" on programmes
  for select to anon, authenticated using (published = true);

create policy "Authenticated can manage programmes" on programmes
  for all to authenticated using (true) with check (true);

create table if not exists programme_registrations (
  id uuid default gen_random_uuid() primary key,
  programme_slug text not null,
  programme_title text,
  name text not null,
  email text not null,
  phone text,
  company text,
  designation text,
  pax integer default 1 check (pax between 1 and 50),
  hrdc_claim boolean default false,
  message text,
  source text default 'website',
  status text default 'new' check (status in ('new','contacted','confirmed','paid','cancelled')),
  consent_pdpa boolean not null default false,
  created_at timestamptz default timezone('utc', now())
);

create index if not exists idx_reg_programme on programme_registrations(programme_slug);
create index if not exists idx_reg_created on programme_registrations(created_at desc);

alter table programme_registrations enable row level security;

create policy "Anonymous can register" on programme_registrations
  for insert to anon, authenticated with check (consent_pdpa = true);

create policy "Authenticated can read registrations" on programme_registrations
  for select to authenticated using (true);

create policy "Authenticated can update registrations" on programme_registrations
  for update to authenticated using (true) with check (true);

-- keep updated_at fresh
create or replace function set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = timezone('utc', now()); return new; end $$;

drop trigger if exists trg_programmes_updated on programmes;
create trigger trg_programmes_updated before update on programmes
  for each row execute function set_updated_at();
