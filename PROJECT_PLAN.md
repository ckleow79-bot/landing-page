# End-of-Line Packaging Automation Company - Landing Page Project Plan

**Business**: End-of-Line Packaging Automation Solutions  
**Location**: Malaysia (HQ)  
**Target Markets**: International | Medical Devices | Pharmacies | Gloves | FMCG  
**Value Proposition**: One-Stop Solution (Design → Manufacturing → Delivery → Installation)

---

## Table of Contents
1. [Site Architecture & Page Structure](#site-architecture--page-structure)
2. [Technical Implementation Plan](#technical-implementation-plan)
3. [Supabase Database Schema](#supabase-database-schema)
4. [Anime.js Animation Plan](#animejs-animation-plan)
5. [Mobile Responsive Strategy](#mobile-responsive-strategy)
6. [Floating Chatbot Features](#floating-chatbot-features)
7. [Open Questions](#open-questions)

---

## Site Architecture & Page Structure

### 1. **Landing Page (Home)** `/index.html`

**Sections** (Top to Bottom):

#### Hero Section
- **Animated company name** (using animejs code)
- **Headline**: "End-to-End Packaging Automation Solutions"
- **Subheadline**: "From Malaysia to the World — Precision Engineering for Medical, Pharmaceutical & FMCG Industries"
- **Primary CTA**: "Get Free Consultation"
- **Secondary CTA**: "View Our Solutions"
- **Background**: Industrial automation imagery/video

#### Industries We Serve
- Medical Devices
- Pharmaceutical Packaging
- Glove Manufacturing
- FMCG Products
- (Icon + brief description for each)

#### One-Stop Solution
- Design & Engineering
- Manufacturing & Fabrication
- Delivery & Logistics
- Installation & Commissioning
- After-Sales Support
- (Visual timeline/process flow)

#### Why Choose Us
- Malaysia-based with global reach
- Industry expertise
- Custom solutions
- Quality assurance
- Technical support

#### Testimonials
- 3-4 client testimonials with company logos
- Star ratings
- Carousel/slider format

#### Featured Projects (Preview)
- 3 latest projects with thumbnails
- "View All Projects" link

#### Newsletter CTA
- "Stay Updated with Industry Insights"
- Email subscription form

#### Contact Section
- Contact form (name, email, company, message)
- Company address (Malaysia)
- Phone, WhatsApp, Email
- Map integration

#### Footer
- Sitemap links
- Social media icons
- Copyright
- Privacy Policy | Terms of Service

---

### 2. **About Us** `/about.html`
- Company Profile
- Mission & Vision
- Core Values
- Milestones/Timeline
- Certifications
- Team/Leadership
- Manufacturing Facility

---

### 3. **Products & Solutions** `/products.html`
- **Product Categories**:
  - Case Packers
  - Palletizers
  - Wrapping Machines
  - Conveying Systems
  - Custom Automation
- Technical specifications
- Downloadable brochures

---

### 4. **Projects Gallery** `/projects.html`
- Filterable gallery by industry
- Case studies with:
  - Client name
  - Challenge
  - Solution provided
  - Results
  - Photos/videos

---

### 5. **Blog/Newsletter** `/blog.html`
- Industry insights
- Company news
- Technical articles
- **Categories**: Industry Trends, Product Updates, Case Studies

---

### 6. **Investors** `/investors.html`
- Company financials
- Annual reports
- Stock information (if applicable)
- Investor contact
- Corporate governance

---

## Technical Implementation Plan

### Technology Stack
- **HTML5** + **CSS3** (Vanilla, no frameworks for simplicity)
- **JavaScript** (Vanilla ES6+)
- **Anime.js** for animations
- **Supabase** for backend (contact form data, newsletter subscriptions)
- **Font Awesome** or **Lucide** for icons
- **Google Fonts** (Inter or similar professional font)

### Project Structure
```
/
├── index.html              # Landing page
├── about.html              # About us
├── products.html           # Products & solutions
├── projects.html           # Projects gallery
├── blog.html               # Blog/Newsletter
├── investors.html          # Investor relations
├── css/
│   ├── main.css           # Global styles
│   ├── responsive.css     # Mobile responsiveness
│   └── animations.css     # Custom animation helpers
├── js/
│   ├── main.js            # Main functionality
│   ├── animations.js      # Anime.js configurations
│   ├── supabase.js        # Supabase client & functions
│   └── chatbot.js         # Floating chatbot
├── assets/
│   ├── images/
│   │   ├── hero/          # Hero backgrounds
│   │   ├── products/      # Product images
│   │   ├── projects/      # Project photos
│   │   ├── icons/         # Custom icons
│   │   └── team/          # Team photos
│   └── documents/         # PDFs, brochures
└── components/
    ├── header.html        # Reusable header
    ├── footer.html        # Reusable footer
    ├── chatbot.html       # Floating chatbot button
    └── contact-form.html  # Reusable contact form
```

---

## Supabase Database Schema

### Table: `contact_submissions`

```sql
CREATE TABLE contact_submissions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  company TEXT,
  phone TEXT,
  industry TEXT, -- Medical, Pharmaceutical, Gloves, FMCG, Other
  message TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  status TEXT DEFAULT 'new' -- new, contacted, resolved
);
```

### Table: `newsletter_subscribers`

```sql
CREATE TABLE newsletter_subscribers (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  company TEXT,
  industry TEXT,
  subscribed_at TIMESTAMP DEFAULT NOW(),
  is_active BOOLEAN DEFAULT true
);
```

### Table: `chat_conversations` (for chatbot)

```sql
CREATE TABLE chat_conversations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  visitor_id TEXT, -- anonymous identifier
  messages JSONB, -- array of messages
  started_at TIMESTAMP DEFAULT NOW(),
  ended_at TIMESTAMP,
  email TEXT, -- if visitor provides contact
  status TEXT DEFAULT 'active' -- active, closed, converted
);
```

---

## Anime.js Animation Plan

### 1. **Hero Text Animation** (Branding Name)

```javascript
import { animate, stagger, splitText } from 'https://esm.sh/animejs';

const { chars } = splitText('.company-name', { words: false, chars: true });

animate(chars, {
  // Property keyframes
  y: [
    { to: '-2.75rem', ease: 'outExpo', duration: 600 },
    { to: 0, ease: 'outBounce', duration: 800, delay: 100 }
  ],
  // Property specific parameters
  rotate: {
    from: '-1turn',
    delay: 0
  },
  delay: stagger(50),
  ease: 'inOutCirc',
  loopDelay: 1000,
  loop: true
});
```

### 2. **Section Reveal Animations**

- **Fade Up**: Elements fade in and move up on scroll
- **Stagger**: List items appear sequentially
- **Counter**: Animated numbers for statistics

### 3. **Scroll-Triggered Animations**

- Industries cards: Fade in from sides
- Timeline: Progressive reveal
- Testimonials: Smooth carousel transitions

### 4. **Micro-interactions**

- Button hover effects (scale, shadow)
- Form input focus animations
- Chatbot button pulse animation

---

## Mobile Responsive Strategy

### Breakpoints

- **Desktop**: 1200px+ (full layout)
- **Tablet**: 768px - 1199px (adjusted grid)
- **Mobile**: < 768px (single column, hamburger menu)

### Mobile Adaptations

| Feature | Desktop | Tablet | Mobile |
|---------|---------|---------|---------|
| Navigation | Horizontal menu | Horizontal menu | Hamburger menu with slide-in drawer |
| Hero | Side-by-side layout | Adjusted spacing | Stacked, smaller text |
| Industries Grid | 4 columns | 2 columns | Single column |
| Timeline | Horizontal | Horizontal | Vertical |
| Contact Form | 2 columns | 2 columns | Full-width, stacked |
| Chatbot | Bottom right | Bottom right | Bottom right (minimized default) |
| Footer | Multi-column | 2 columns | Accordion-style collapsible |

### Performance Optimizations

- Lazy loading for images
- Optimized image sizes per breakpoint
- Touch-friendly tap targets (min 44px)
- Reduced animation complexity on mobile

---

## Floating Chatbot Features

### Position
Bottom Right (fixed position)

### Features

#### Minimized State
- Chat icon with pulse animation
- Badge notification for unread messages

#### Expanded State
- Chat window with:
  - Welcome message
  - Quick reply buttons (FAQs)
  - Live chat or email capture
  - Form for detailed inquiries

#### Chat Flow
1. Welcome: "Hi! How can we help you with your packaging automation needs?"
2. Quick Options:
   - Get a Quote
   - View Products
   - Technical Support
   - Schedule a Call
3. Capture email for follow-up if offline

---

## Open Questions

Before implementation begins, please clarify:

### 1. Company Name
What's the actual company name for the hero animation?

### 2. Branding
- Do you have an existing logo?
- Preferred color scheme? (Industrial colors: blue, grey, orange?)

### 3. Supabase Setup
- Do you have a Supabase project already?
- Should I include setup instructions for the database?

### 4. Content
- Do you have existing testimonials?
- Project photos/case studies ready?
- Team photos for About page?

### 5. Chatbot
- Simple FAQ bot or integration with a service (e.g., Tidio, Intercom)?
- Or custom-built with predefined responses?

### 6. Hosting
Where will this be deployed? (Netlify, Vercel, own server?)

---

## Implementation Checklist

### Phase 1: Setup & Foundation
- [ ] Create project structure
- [ ] Set up Supabase project and tables
- [ ] Create base HTML templates
- [ ] Implement global CSS styles
- [ ] Set up anime.js integration

### Phase 2: Core Pages
- [ ] Build Landing Page (Home)
- [ ] Build About Us page
- [ ] Build Products page
- [ ] Implement navigation and footer components

### Phase 3: Advanced Features
- [ ] Implement chatbot
- [ ] Build Projects Gallery
- [ ] Create Blog/Newsletter pages
- [ ] Build Investors page

### Phase 4: Polish & Optimization
- [ ] Mobile responsiveness testing
- [ ] Animation fine-tuning
- [ ] Performance optimization
- [ ] Cross-browser testing

### Phase 5: Launch Preparation
- [ ] Content population
- [ ] SEO optimization
- [ ] Analytics setup
- [ ] Final testing and deployment

---

## Design Principles

1. **Professional & Industrial**: Clean, modern design reflecting precision engineering
2. **Trust & Credibility**: Testimonials, certifications, case studies prominently displayed
3. **Global Appeal**: Professional imagery and language suitable for international clients
4. **Easy Navigation**: Clear information architecture for quick access to relevant content
5. **Mobile-First**: Optimal experience across all devices

---

## Success Metrics

- **Conversion**: Contact form submissions
- **Engagement**: Time on site, pages per session
- **Lead Quality**: Industry-specific inquiries
- **Mobile Traffic**: Responsive design effectiveness
- **Performance**: Page load speed (< 3 seconds)

---

*Document Version: 1.0*  
*Last Updated: March 2026*
