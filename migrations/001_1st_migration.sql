-- Migration to create contact_submissions table for the Contact Us form

create table contact_submissions (
  id uuid default gen_random_uuid() primary key,
  name text not null,
  email text not null,
  company text,
  phone text,
  industry text,
  message text not null,
  type text default 'general',
  status text default 'new',
  created_at timestamp with time zone default timezone('utc'::text, now()),
  updated_at timestamp with time zone default timezone('utc'::text, now())
);

-- Enable Row Level Security (RLS)
alter table contact_submissions enable row level security;

-- Create policy to allow inserts from anonymous users
create policy "Allow anonymous inserts" on contact_submissions
  for insert to anon with check (true);

-- Create policy to allow select only for authenticated users
create policy "Allow authenticated select" on contact_submissions
  for select to authenticated using (true);

-- Create indexes for faster lookups
create index idx_contact_email on contact_submissions(email);
create index idx_contact_created_at on contact_submissions(created_at desc);
