# End-of-Line Packaging Automation Company Landing Page

## Overview
Professional landing page for a packaging automation company serving Medical Devices, Pharmaceutical, Gloves, and FMCG industries in Malaysia and Southeast Asia.

## Features

### Design & UI
- **Responsive Design**: Mobile-first approach with breakpoints at 1200px, 991px, 767px, and 480px
- **Modern Aesthetics**: Clean, professional design with gradient backgrounds and smooth animations
- **Dark/Light Contrast**: Accessible color scheme with proper contrast ratios

### Animations
- **Anime.js Integration**: Advanced text animations, scroll-triggered reveals, and micro-interactions
- **CSS Animations**: Smooth transitions, hover effects, and loading states
- **Performance Optimized**: Hardware-accelerated transforms and will-change properties

### Functionality
- **Floating Chatbot**: Interactive chat with quick replies and conversation flow
- **Contact Forms**: Supabase-integrated forms with validation
- **Newsletter Subscription**: Email capture with duplicate checking
- **Project Filtering**: Category-based project gallery filtering

### Technical Stack
- **HTML5**: Semantic markup with accessibility features
- **CSS3**: CSS Grid, Flexbox, CSS Variables, and custom properties
- **JavaScript (ES6+)**: Modern JS with async/await and modular architecture
- **Supabase**: Backend-as-a-Service for database and authentication
- **Anime.js**: Lightweight animation library
- **Font Awesome**: Icon library
- **Google Fonts**: Inter font family

## Project Structure

```
Landing Page/
├── index.html              # Homepage
├── about.html              # About Us page
├── products.html           # Products & Solutions page
├── projects.html           # Projects gallery page
├── blog.html               # Blog & News page
├── investors.html          # Investor Relations page
├── css/
│   ├── main.css           # Global styles and variables
│   ├── pages.css          # Page-specific styles
│   ├── responsive.css     # Mobile responsive styles
│   ├── animations.css     # Animation keyframes and effects
│   └── chatbot.css        # Chatbot component styles
├── js/
│   ├── main.js            # Main JavaScript functionality
│   ├── animations.js      # Anime.js animations
│   ├── supabase.js        # Supabase integration
│   └── chatbot.js         # Chatbot logic
├── components/
│   ├── header.html        # Reusable header component
│   ├── footer.html        # Reusable footer component
│   └── chatbot.html       # Chatbot component
├── assets/
│   ├── images/            # Image assets
│   └── documents/         # PDF downloads
├── robots.txt             # Search engine crawling rules
├── sitemap.xml            # XML sitemap for SEO
├── SUPABASE_SETUP.md      # Supabase configuration guide
└── README.md              # This file
```

## Quick Start

### 1. Local Development
```bash
# Clone or download the project
cd "Landing Page"

# Install dependencies
npm install

# Start development server
npm start
```

### 2. Supabase Setup
1. Create a Supabase project at https://supabase.com
2. Follow the instructions in `SUPABASE_SETUP.md`
3. Update `js/supabase.js` with your credentials

### 3. Content Customization
1. Replace placeholder text `[Your Company Name]` with your actual company name
2. Update contact information (address, phone, email)
3. Add your company images to `assets/images/`
4. Customize colors in `css/main.css` CSS variables

## Customization Guide

### Colors
Edit CSS variables in `css/main.css`:
```css
:root {
    --primary-color: #1a365d;     /* Main brand color */
    --secondary-color: #ed8936;   /* Accent/CTA color */
    --accent-color: #38a169;      /* Success/positive color */
}
```

### Content
Replace placeholder content in all HTML files:
- Company name and logo
- Contact information
- Product descriptions
- Team member information
- Project case studies

### Images
Add your images to `assets/images/`:
- `hero-bg.jpg` - Hero background
- `facility.jpg` - Manufacturing facility
- `project-*.jpg` - Project photos (1.jpg through 6c.jpg)
- `team-*.jpg` - Team member photos
- `product-*.jpg` - Product images

## Deployment

### Option 1: Static Hosting (Recommended)
- **Netlify**: Drag and drop the folder
- **Vercel**: Connect GitHub repository
- **GitHub Pages**: Enable in repository settings
- **Cloudflare Pages**: Connect repository

### Option 2: Traditional Hosting
Upload all files via FTP/SFTP to your web server.

### Build for Production
```bash
# Minify CSS and JS
npm run build

# Optimize images
npm run optimize:images
```

## Browser Support
- Chrome/Edge (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance
- Lazy loading for images
- Minified assets in production
- Optimized animations (reduced motion support)
- Efficient CSS with CSS Grid and Flexbox

## SEO Features
- Semantic HTML5 markup
- Meta tags for all pages
- Open Graph tags for social sharing
- XML sitemap
- Robots.txt
- Structured data ready (Schema.org)

## Accessibility
- ARIA labels for interactive elements
- Keyboard navigation support
- Focus indicators
- Color contrast compliance (WCAG 2.1 AA)
- Reduced motion support

## Security
- Content Security Policy ready
- HTTPS recommended
- Form validation
- XSS prevention in templates

## License
MIT License - See LICENSE file for details

## Support
For issues or questions:
- Check `SUPABASE_SETUP.md` for database configuration
- Review browser console for JavaScript errors
- Ensure all dependencies are properly loaded

## Roadmap
- [ ] Add blog post template page
- [ ] Implement dark mode toggle
- [ ] Add multi-language support
- [ ] Integrate with CRM system
- [ ] Add live chat integration option

## Credits
- Design & Development: Your Company Name
- Icons: Font Awesome
- Fonts: Google Fonts (Inter)
- Animation Library: Anime.js
- Backend: Supabase

---

**Version**: 1.0.0  
**Last Updated**: March 2026  
**Status**: Production Ready