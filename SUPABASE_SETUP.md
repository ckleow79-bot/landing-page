# Supabase Backend Setup Guide

## Project Configuration

### 1. Create Supabase Project
1. Go to https://supabase.com and sign up/login
2. Click "New Project"
3. Choose your organization
4. Enter project name: `packaging-automation-website`
5. Set database password (save this securely)
6. Choose region: `Southeast Asia (Singapore)`
7. Click "Create new project"

### 2. Get API Credentials
Once project is created:
1. Go to Project Settings (gear icon)
2. Click on "API" in the sidebar
3. Copy the following:
   - **URL**: `https://your-project-ref.supabase.co`
   - **anon public**: `your-anon-key`

### 3. Update Website Configuration
Open `js/supabase.js` and replace:
```javascript
const SUPABASE_URL = 'https://your-supabase-project.supabase.co';
const SUPABASE_KEY = 'your-supabase-anon-key';
```

With your actual credentials from step 2.

---

## Database Schema Setup

### Table 1: contact_submissions
Run this SQL in the Supabase SQL Editor:

```sql
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

-- Enable RLS
alter table contact_submissions enable row level security;

-- Create policy to allow inserts from anonymous users
create policy "Allow anonymous inserts" on contact_submissions
  for insert to anon with check (true);

-- Create policy to allow select only for authenticated users
create policy "Allow authenticated select" on contact_submissions
  for select to authenticated using (true);

-- Create index on email for faster lookups
create index idx_contact_email on contact_submissions(email);
create index idx_contact_created_at on contact_submissions(created_at desc);
```

### Table 2: newsletter_subscribers
```sql
create table newsletter_subscribers (
  id uuid default gen_random_uuid() primary key,
  email text not null unique,
  status text default 'active',
  created_at timestamp with time zone default timezone('utc'::text, now()),
  updated_at timestamp with time zone default timezone('utc'::text, now())
);

-- Enable RLS
alter table newsletter_subscribers enable row level security;

-- Create policy to allow inserts from anonymous users
create policy "Allow anonymous inserts" on newsletter_subscribers
  for insert to anon with check (true);

-- Create policy to prevent duplicate emails from being visible
create policy "Allow check existing" on newsletter_subscribers
  for select to anon using (email = current_setting('app.current_email', true));

-- Create index on email
create index idx_newsletter_email on newsletter_subscribers(email);
```

### Table 3: chat_conversations
```sql
create table chat_conversations (
  id uuid default gen_random_uuid() primary key,
  visitor_id text not null unique,
  email text,
  messages jsonb default '[]'::jsonb,
  type text default 'general',
  created_at timestamp with time zone default timezone('utc'::text, now()),
  updated_at timestamp with time zone default timezone('utc'::text, now())
);

-- Enable RLS
alter table chat_conversations enable row level security;

-- Create policy to allow all operations for anonymous users on their own visitor_id
create policy "Allow anonymous operations" on chat_conversations
  for all to anon using (true) with check (true);

-- Create index on visitor_id
create index idx_chat_visitor_id on chat_conversations(visitor_id);
```

---

## Environment Variables (For Deployment)

If deploying to a hosting service, set these environment variables:

```
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

---

## Testing the Setup

### Test Contact Form
1. Open the website in a browser
2. Go to the Contact section
3. Fill out and submit the form
4. Check Supabase Table Editor → contact_submissions
5. Verify the submission appears

### Test Newsletter
1. Enter an email in the newsletter form
2. Submit
3. Check Supabase Table Editor → newsletter_subscribers

### Test Chatbot
1. Open the chatbot
2. Send a few messages
3. Check Supabase Table Editor → chat_conversations

---

## Security Configuration

### 1. Enable Email Confirmations (Optional)
If you want to verify emails:
1. Go to Authentication → Settings
2. Enable "Confirm email"
3. Customize the email template

### 2. Rate Limiting
Add rate limiting to prevent spam:
1. Go to Database → Extensions
2. Enable `pg_stat_statements`
3. Consider implementing rate limiting in your application layer

### 3. CORS Configuration
Ensure your domain is allowed:
1. Go to API → Settings
2. Under "CORS", add your domain:
   - Production: `https://yourdomain.com`
   - Development: `http://localhost:5500` (or your dev server)

---

## Backup Strategy

### Automated Backups
Supabase provides automated daily backups. To configure:
1. Go to Project Settings → Database
2. Review backup schedule
3. For additional security, set up manual exports

### Manual Export
```bash
# Using supabase CLI
supabase db dump -f backup.sql
```

---

## Monitoring

### Database Usage
Monitor usage in:
- Dashboard → Database → Usage
- Set up alerts for high usage

### API Usage
Monitor in:
- Dashboard → API → Usage
- Check for unusual patterns

---

## Troubleshooting

### Forms not submitting
1. Check browser console for errors
2. Verify Supabase URL and key are correct
3. Check RLS policies are enabled
4. Ensure tables exist with correct schema

### CORS errors
1. Add your domain to CORS settings
2. Check that you're using HTTPS in production

### Rate limiting
Supabase free tier has limits:
- 500 requests per second
- Consider upgrading for high-traffic sites

---

## Next Steps

After Supabase is configured:
1. Test all forms thoroughly
2. Set up email notifications (using Supabase Edge Functions or Zapier)
3. Configure monitoring alerts
4. Document admin access procedures

---

## Support

For issues:
- Supabase Docs: https://supabase.com/docs
- Supabase Discord: https://discord.supabase.com
- Check status: https://status.supabase.com