# Pre-Launch Deployment Checklist

## Content & Copy
- [ ] Replace all `[Your Company Name]` placeholders
- [ ] Update company address and contact details
- [ ] Add real phone numbers and email addresses
- [ ] Write custom company description (not template text)
- [ ] Add real team member names and bios
- [ ] Update milestones with actual dates and achievements
- [ ] Write real testimonials (or remove if not available)
- [ ] Add actual project case studies with real data

## Images & Assets
- [ ] Create/add company logo (logo.svg/png)
- [ ] Add hero background image (hero-bg.jpg)
- [ ] Add facility/manufacturing photos
- [ ] Add product photos (minimum 9 images)
- [ ] Add project photos (minimum 18 images)
- [ ] Add team member photos
- [ ] Add Open Graph images for social sharing (og-*.jpg)
- [ ] Create favicon.ico and apple-touch-icon.png
- [ ] Optimize all images (< 200KB each, WebP preferred)
- [ ] Add alt text to all images

## Supabase Setup
- [ ] Create Supabase project
- [ ] Get API URL and anon key
- [ ] Update js/supabase.js with credentials
- [ ] Run SQL scripts to create tables
- [ ] Configure RLS policies
- [ ] Test contact form submission
- [ ] Test newsletter subscription
- [ ] Test chatbot conversation storage
- [ ] Set up email notifications (optional)

## SEO Configuration
- [ ] Update page titles with company name
- [ ] Write unique meta descriptions for each page
- [ ] Update Open Graph tags with company info
- [ ] Update Twitter Card meta tags
- [ ] Update sitemap.xml with actual domain
- [ ] Update robots.txt with actual domain
- [ ] Update canonical URLs
- [ ] Add Google Analytics 4 tracking code
- [ ] Set up Google Search Console
- [ ] Submit sitemap to Google

## Domain & Hosting
- [ ] Purchase domain name
- [ ] Set up DNS records
- [ ] Configure SSL certificate (HTTPS)
- [ ] Choose hosting provider
- [ ] Upload files to server
- [ ] Test site on live domain
- [ ] Configure www to non-www redirect (or vice versa)
- [ ] Set up email hosting if needed

## Legal & Compliance
- [ ] Create Privacy Policy page
- [ ] Create Terms of Service page
- [ ] Create Cookie Policy page
- [ ] Add cookie consent banner
- [ ] Ensure GDPR compliance for forms
- [ ] Add company registration number
- [ ] Add copyright notice with current year

## Testing

### Cross-Browser Testing
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Chrome Mobile (iOS)
- [ ] Safari Mobile (iOS)
- [ ] Chrome Mobile (Android)

### Functionality Testing
- [ ] All navigation links work
- [ ] Mobile menu opens/closes
- [ ] Contact forms submit successfully
- [ ] Newsletter form works
- [ ] Chatbot opens and flows work
- [ ] Downloadable files work (PDFs)
- [ ] Social media links work
- [ ] Phone numbers are clickable (tel:)
- [ ] Email links work (mailto:)
- [ ] WhatsApp link works

### Responsive Testing
- [ ] Desktop 1920px
- [ ] Desktop 1440px
- [ ] Desktop 1280px
- [ ] Tablet 1024px (landscape)
- [ ] Tablet 768px (portrait)
- [ ] Mobile 767px
- [ ] Mobile 480px
- [ ] Mobile 375px (iPhone SE)

### Performance Testing
- [ ] Page load speed < 3 seconds
- [ ] Images load properly
- [ ] No 404 errors in console
- [ ] No JavaScript errors
- [ ] Lazy loading works
- [ ] Smooth scroll works
- [ ] Animations are smooth (60fps)

### Accessibility Testing
- [ ] All images have alt text
- [ ] Form inputs have labels
- [ ] Color contrast meets WCAG AA
- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] Screen reader compatible
- [ ] Reduced motion support works

## Security
- [ ] HTTPS enabled (SSL certificate)
- [ ] .htaccess security headers configured
- [ ] Sensitive files protected (package.json, .md files)
- [ ] Form validation working
- [ ] No exposed API keys (use env vars)
- [ ] XSS prevention in place
- [ ] Secure Supabase configuration

## Post-Launch Tasks
- [ ] Test forms one more time on live site
- [ ] Verify Supabase is receiving data
- [ ] Set up Google Analytics goals
- [ ] Configure uptime monitoring (UptimeRobot, Pingdom)
- [ ] Set up backup strategy
- [ ] Create admin email for form notifications
- [ ] Document admin access procedures
- [ ] Train team on content updates
- [ ] Schedule regular maintenance
- [ ] Plan content update calendar

## Marketing Setup
- [ ] Set up Google Business Profile
- [ ] Create social media accounts
- [ ] Add website to social media profiles
- [ ] Create email signature with website link
- [ ] Add website to business cards
- [ ] Set up email marketing (Mailchimp, etc.)

## Emergency Contacts
- Hosting provider support: ___________
- Domain registrar support: ___________
- Developer/Agency: ___________
- Supabase support: https://supabase.com/support

## Notes
- Keep backups of original files
- Document any custom modifications
- Save all login credentials securely
- Set calendar reminders for SSL renewal
- Schedule quarterly security reviews