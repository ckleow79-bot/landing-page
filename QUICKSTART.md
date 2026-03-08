# Quick Start Guide

Get your website running in minutes!

---

## 🚀 Quick Start (5 Minutes)

### 1. Local Development (2 minutes)

```bash
# Navigate to project directory
cd "Landing Page"

# Install dependencies
npm install

# Start development server
npm start
```

**Result**: Your website will be live at `http://localhost:5500`

---

### 2. Customize Content (10 minutes)

#### Step 1: Update Company Information
1. Open `index.html` in a text editor
2. Find `[Your Company Name]` and replace with your actual company name
3. Update address, phone numbers, and email addresses
4. Replace placeholder images with your own (in `assets/images/`)

#### Step 2: Update Supabase Configuration
1. Open `js/supabase.js`
2. Replace `SUPABASE_URL` and `SUPABASE_KEY` with your credentials
3. Run the SQL scripts in `SUPABASE_SETUP.md` in your Supabase dashboard

#### Step 3: Update Meta Tags
1. Update page titles, descriptions, and URLs in all HTML files
2. Replace `[yourcompany.com]` with your actual domain

---

### 3. Add Images (5 minutes)

```bash
# Your images should go here:
assets/images/
├── logo.png (300x300px)
├── hero-bg.jpg (1920x1080px)
├── project-*.jpg (multiple files)
├── team-*.jpg (multiple files)
└── favicon.ico (32x32px)
```

---

## 📋 Before Launch Checklist

### Must Do Before Going Live:
- [ ] Replace all `[Your Company Name]` placeholders
- [ ] Add actual company contact information
- [ ] Set up Supabase and test form submissions
- [ ] Add all product images
- [ ] Add project case study images
- [ ] Add team member photos
- [ ] Set up Google Analytics
- [ ] Configure Google Search Console
- [ ] Test all forms work
- [ ] Test all links work
- [ ] Test on multiple devices
- [ ] Purchase domain
- [ ] Set up hosting

---

## 🌐 Deployment Options

### Option 1: Netlify (Easiest)

```bash
# 1. Create Netlify account
# 2. Install Netlify CLI (optional)
npm install -g netlify-cli

# 3. Login and deploy
netlify login
netlify deploy --prod
```

Or simply drag and drop the folder to https://app.netlify.com/drop

**Time**: 5 minutes  
**Cost**: Free (with limits)

---

### Option 2: Vercel

```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Deploy
vercel --prod
```

Or connect your GitHub repository in Vercel dashboard

**Time**: 10 minutes  
**Cost**: Free (with limits)

---

### Option 3: Traditional Hosting (cPanel)

1. Purchase hosting (shared hosting recommended)
2. Upload files via FTP or File Manager
3. Configure domain in hosting control panel
4. Install SSL certificate (Let's Encrypt recommended)
5. Update DNS records

**Time**: 15-30 minutes  
**Cost**: $3-10/month

---

## 🔧 Configuration Steps

### 1. Supabase Setup

```sql
-- Run these in Supabase SQL Editor:
CREATE TABLE contact_submissions (...);
CREATE TABLE newsletter_subscribers (...);
CREATE TABLE chat_conversations (...);
```

See `SUPABASE_SETUP.md` for complete instructions.

---

### 2. Google Analytics Setup

```javascript
// Replace GA_MEASUREMENT_ID in index.html with your actual ID
// Example: gtag('config', 'G-XXXXXXXXXX');

// Go to: https://analytics.google.com/
// 1. Create account
// 2. Create property
// 3. Get Measurement ID
// 4. Paste into HTML file
```

---

### 3. Domain Configuration

### Netlify:
1. Add custom domain in Netlify dashboard
2. Update DNS records to Netlify nameservers

### Vercel:
1. Add custom domain in Vercel dashboard
2. Update A records and CNAME

### Traditional Hosting:
1. Update A record: `@ → 1.2.3.4`
2. Update CNAME: `www → 1.2.3.4`
3. Add SSL certificate

---

## 🎨 Customization Guide

### Change Colors
Edit `css/main.css`:
```css
:root {
    --primary-color: #1a365d;  /* Navy blue */
    --secondary-color: #ed8936; /* Orange */
}
```

### Change Company Name
Find and replace `[Your Company Name]` in all HTML files

### Add New Pages
1. Copy any HTML file
2. Rename to your new page
3. Update navigation in `components/header.html`
4. Add to sitemap.xml

---

## 📊 Monitoring Setup

### 1. Google Analytics
- [ ] Create property
- [ ] Get measurement ID
- [ ] Add to HTML
- [ ] Test with browser console

### 2. Google Search Console
- [ ] Verify domain ownership
- [ ] Submit sitemap
- [ ] Add robots.txt
- [ ] Check coverage

### 3. Uptime Monitoring
- [ ] Set up UptimeRobot
- [ ] Monitor website availability
- [ ] Set up email alerts

---

## 🐛 Troubleshooting

### Forms Not Submitting
1. Check Supabase configuration
2. Check browser console for errors
3. Verify RLS policies in Supabase
4. Test with browser DevTools network tab

### Images Not Loading
1. Check image paths are correct
2. Check image files exist in assets/images/
3. Check image sizes (max 200KB recommended)

### Animations Not Working
1. Check Anime.js is loaded
2. Check for JavaScript errors in console
3. Verify CSS animations file is linked

### Mobile Menu Not Working
1. Check main.js is loaded
2. Check for JavaScript conflicts
3. Test on actual mobile device

---

## 📞 Need Help?

### Documentation
- **README.md**: General information
- **SUPABASE_SETUP.md**: Database configuration
- **AGENTS.md**: Development commands
- **BROWSER_TESTING.md**: Testing guide
- **CONTENT_TEMPLATES.md**: Content examples

### Resources
- **Supabase Docs**: https://supabase.com/docs
- **Anime.js Docs**: https://animejs.com/documentation
- **Netlify**: https://docs.netlify.com
- **Vercel**: https://vercel.com/docs

---

## ✅ Next Steps

### Week 1:
- [ ] Customize all content
- [ ] Add all images
- [ ] Test forms locally
- [ ] Set up Supabase

### Week 2:
- [ ] Deploy to staging
- [ ] Test on all browsers
- [ ] Test on mobile devices
- [ ] Fix any issues

### Week 3:
- [ ] Deploy to production
- [ ] Set up Google Analytics
- [ ] Submit to Google Search Console
- [ ] Monitor performance

---

**Last Updated**: March 8, 2026  
**Quick Start Version**: 1.0