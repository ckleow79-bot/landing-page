-- 003: lock website data to admins only.
--
-- Before: any signed-in Supabase user ("authenticated") could read every enquiry and
-- registration and edit programmes. Because the anon key is public and email sign-up
-- is on by default, anyone could create an account and read client personal data.
--
-- After: only users whose app_metadata.role = 'admin' can read or change these tables.
-- app_metadata can only be set with the service-role key (Dashboard > Authentication >
-- Users > user > Raw app meta data: {"role": "admin"}), never by the user themselves.
--
-- ALSO DO IN THE DASHBOARD: Authentication > Providers > Email > turn OFF "Allow new users to sign up".

create or replace function public.is_admin() returns boolean
language sql stable as $$
  select coalesce((auth.jwt() -> 'app_metadata' ->> 'role') = 'admin', false)
$$;

-- contact_submissions: anyone may submit, only admins may read or change
drop policy if exists "Allow authenticated select" on contact_submissions;
create policy "Admins read enquiries" on contact_submissions for select to authenticated using (public.is_admin());
create policy "Admins update enquiries" on contact_submissions for update to authenticated using (public.is_admin()) with check (public.is_admin());

-- programmes: public reads published rows, only admins manage
drop policy if exists "Authenticated can manage programmes" on programmes;
create policy "Admins manage programmes" on programmes for all to authenticated using (public.is_admin()) with check (public.is_admin());
-- links on programme cards must be https
alter table programmes drop constraint if exists programmes_https_links;
alter table programmes add constraint programmes_https_links check (
  (register_url is null or register_url = '' or register_url like 'https://%') and
  (brochure_url is null or brochure_url = '' or brochure_url like 'https://%'));

-- programme_registrations: anyone may register with consent, only admins read or update
drop policy if exists "Authenticated can read registrations" on programme_registrations;
drop policy if exists "Authenticated can update registrations" on programme_registrations;
create policy "Admins read registrations" on programme_registrations for select to authenticated using (public.is_admin());
create policy "Admins update registrations" on programme_registrations for update to authenticated using (public.is_admin()) with check (public.is_admin());

-- newsletter: insert only (duplicates rejected by the unique email), admins read
create table if not exists newsletter_subscribers (
  id uuid default gen_random_uuid() primary key,
  email text not null unique,
  consent boolean not null default false,
  source text default 'website',
  created_at timestamptz default timezone('utc', now())
);
alter table newsletter_subscribers enable row level security;
drop policy if exists "Anyone can subscribe" on newsletter_subscribers;
create policy "Anyone can subscribe" on newsletter_subscribers for insert to anon, authenticated with check (consent = true);
create policy "Admins read subscribers" on newsletter_subscribers for select to authenticated using (public.is_admin());

-- chat transcripts are no longer collected (the assistant stores nothing)
drop table if exists chat_conversations;
