# AGENTS.md

## Project Information
- **Project Name**: End-of-Line Packaging Automation Company Landing Page
- **Type**: Static HTML/CSS/JS Website with Supabase Backend
- **Framework**: Vanilla JavaScript with Anime.js animations
- **Backend**: Supabase (PostgreSQL + Auth + Realtime)

## Development Commands

### Start Development Server
```bash
npm install
npm start
# Serves on http://localhost:5500
```

### Build for Production
```bash
npm run build
# Minifies CSS and JS files
```

### Optimize Images
```bash
npm run optimize:images
# Compresses images in assets/images/
```

## Project Structure
```
Landing Page/
├── *.html              # 6 main pages
├── css/               # 5 CSS files
│   ├── main.css      # Global styles, variables
│   ├── pages.css     # Page-specific layouts
│   ├── responsive.css # Mobile breakpoints
│   ├── animations.css # Keyframes & effects
│   └── chatbot.css   # Chatbot styles
├── js/               # 4 JS files
│   ├── main.js       # Core functionality
│   ├── animations.js # Anime.js animations
│   ├── supabase.js   # Database integration
│   └── chatbot.js    # Chatbot logic
├── components/       # Reusable components
│   ├── header.html
│   ├── footer.html
│   └── chatbot.html
└── assets/          # Images & documents
```

## Key Features

### 1. Responsive Design
- Breakpoints: 1200px, 991px, 767px, 480px
- Mobile-first approach
- Hamburger menu on mobile
- Touch-friendly tap targets (min 44px)

### 2. Animations (Anime.js)
- Hero text character animation
- Scroll-triggered section reveals
- Stagger animations for grids
- Micro-interactions on hover
- Performance optimized with will-change

### 3. Supabase Integration
- Contact form submissions
- Newsletter subscriptions
- Chat conversation storage
- Row Level Security (RLS) enabled

### 4. Chatbot
- Floating chat interface
- Quick reply options
- Conversation flow logic
- Email capture for offline mode
- Local storage + Supabase sync

### 5. SEO
- Semantic HTML5
- Meta tags on all pages
- Open Graph tags
- XML sitemap
- Robots.txt
- Canonical URLs

## CSS Variables (Main Colors)
```css
--primary-color: #1a365d;      /* Navy blue */
--primary-light: #2c5282;
--primary-dark: #0f2942;
--secondary-color: #ed8936;    /* Orange */
--secondary-light: #f6ad55;
--secondary-dark: #c05621;
--accent-color: #38a169;       /* Green */
```

## Important Files to Update

### Before Launch:
1. **js/supabase.js**: Add your Supabase URL and API key
2. **All HTML files**: Replace placeholder content:
   - `[Your Company Name]` → Actual company name
   - `[Company Address]` → Real address
   - `+60 XX-XXXX XXXX` → Real phone numbers
   - `info@yourcompany.com` → Real email
   - `https://yourcompany.com` → Real domain

3. **assets/images/**: Add actual images:
   - hero-bg.jpg
   - facility.jpg
   - project-*.jpg (multiple)
   - team-*.jpg (multiple)
   - product-*.jpg (multiple)
   - favicon.ico

4. **sitemap.xml**: Update URLs to your domain
5. **robots.txt**: Update sitemap URL

### SEO Configuration:
- Update Open Graph image URLs
- Add Google Analytics tracking code
- Set up Google Search Console
- Create and submit XML sitemap

## Testing Checklist

### Functionality:
- [ ] All navigation links work
- [ ] Contact forms submit to Supabase
- [ ] Newsletter subscription works
- [ ] Chatbot opens/closes and flows work
- [ ] Mobile menu toggles correctly
- [ ] Scroll animations trigger properly
- [ ] Testimonials carousel works

### Responsive:
- [ ] Test on desktop (1920px, 1440px, 1280px)
- [ ] Test on tablet (991px, 768px)
- [ ] Test on mobile (767px, 480px, 375px)
- [ ] Touch targets are adequate
- [ ] Text is readable at all sizes

### Performance:
- [ ] Images are optimized (< 200KB each)
- [ ] CSS is minified for production
- [ ] JS is minified for production
- [ ] Lazy loading works on images
- [ ] Page load < 3 seconds

### Accessibility:
- [ ] All images have alt text
- [ ] Form labels are present
- [ ] Focus indicators visible
- [ ] Keyboard navigation works
- [ ] Color contrast meets WCAG AA

## Deployment

### Static Hosting (Recommended):
1. **Netlify**: Drag and drop folder
2. **Vercel**: Connect GitHub repo
3. **Cloudflare Pages**: Connect repo
4. **GitHub Pages**: Enable in settings

### Traditional Hosting:
1. Upload all files via FTP
2. Ensure .htaccess is uploaded
3. Configure SSL certificate
4. Test all forms and functionality

## Post-Launch:
1. Set up Google Analytics 4
2. Configure Google Search Console
3. Submit sitemap to Google
4. Test all contact forms receive data
5. Monitor Supabase usage
6. Set up uptime monitoring

## Troubleshooting

### Common Issues:

**Forms not submitting:**
- Check Supabase URL and key in js/supabase.js
- Verify RLS policies are enabled
- Check browser console for errors

**Animations not working:**
- Ensure Anime.js library loaded
- Check for JavaScript errors in console
- Verify CSS animations file is linked

**Chatbot not opening:**
- Check chatbot.js is loaded
- Verify chatbot.html component exists
- Check z-index values

**Mobile menu not working:**
- Verify main.js is loaded
- Check for JavaScript errors
- Test on actual mobile device

## Contact
For questions about this project, refer to:
- README.md for general info
- SUPABASE_SETUP.md for database setup
- PROGRESS_PLAN.md for development roadmap