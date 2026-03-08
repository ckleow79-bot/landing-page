/**
 * Main JavaScript File
 * End-of-Line Packaging Automation Company Landing Page
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all modules
    initHeader();
    initMobileMenu();
    initScrollAnimations();
    initTestimonialsCarousel();
    initSmoothScroll();
    initScrollTopButton();
    initHeaderShadow();
    loadComponents();
});

/**
 * Load reusable components (header, footer, chatbot)
 */
function loadComponents() {
    // Load Header
    const headerContainer = document.getElementById('header-container');
    if (headerContainer) {
        fetch('components/header.html')
            .then(response => response.text())
            .then(html => {
                headerContainer.innerHTML = html;
                initHeader(); // Re-initialize header functionality
                initMobileMenu(); // Re-initialize mobile menu
            })
            .catch(error => console.error('Error loading header:', error));
    }

    // Load Footer
    const footerContainer = document.getElementById('footer-container');
    if (footerContainer) {
        fetch('components/footer.html')
            .then(response => response.text())
            .then(html => {
                footerContainer.innerHTML = html;
            })
            .catch(error => console.error('Error loading footer:', error));
    }

    // Load Chatbot
    const chatbotContainer = document.getElementById('chatbot-container');
    if (chatbotContainer) {
        fetch('components/chatbot.html')
            .then(response => response.text())
            .then(html => {
                chatbotContainer.innerHTML = html;
                if (typeof initChatbot === 'function') {
                    initChatbot();
                }
            })
            .catch(error => console.error('Error loading chatbot:', error));
    }
}

/**
 * Initialize Header Functionality
 */
function initHeader() {
    const header = document.querySelector('.header');
    if (!header) return;

    // Add scroll class on scroll
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });
}

/**
 * Initialize Mobile Menu
 */
function initMobileMenu() {
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const navMenu = document.querySelector('.nav-menu');
    
    if (!menuToggle || !navMenu) return;

    menuToggle.addEventListener('click', () => {
        navMenu.classList.toggle('active');
        document.body.classList.toggle('menu-open');
        
        // Animate hamburger to X
        const spans = menuToggle.querySelectorAll('span');
        if (navMenu.classList.contains('active')) {
            spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
            spans[1].style.opacity = '0';
            spans[2].style.transform = 'rotate(-45deg) translate(7px, -6px)';
        } else {
            spans[0].style.transform = 'none';
            spans[1].style.opacity = '1';
            spans[2].style.transform = 'none';
        }
    });

    // Close menu when clicking on a link
    const navLinks = navMenu.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navMenu.classList.remove('active');
            document.body.classList.remove('menu-open');
            
            const spans = menuToggle.querySelectorAll('span');
            spans[0].style.transform = 'none';
            spans[1].style.opacity = '1';
            spans[2].style.transform = 'none';
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!menuToggle.contains(e.target) && !navMenu.contains(e.target)) {
            navMenu.classList.remove('active');
            document.body.classList.remove('menu-open');
            
            const spans = menuToggle.querySelectorAll('span');
            spans[0].style.transform = 'none';
            spans[1].style.opacity = '1';
            spans[2].style.transform = 'none';
        }
    });
}

/**
 * Initialize Scroll Animations using Intersection Observer
 */
function initScrollAnimations() {
    const animatedElements = document.querySelectorAll(
        '.reveal, .reveal-left, .reveal-right, .reveal-scale, .stagger-children, ' +
        '.industry-card, .timeline-step, .differentiator-card, .testimonial-card'
    );

    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active', 'visible');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    animatedElements.forEach(el => observer.observe(el));

    // Animate timeline line
    const timelineLine = document.querySelector('.timeline-line');
    if (timelineLine) {
        const lineObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    lineObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });
        
        lineObserver.observe(timelineLine);
    }
}

/**
 * Initialize Testimonials Carousel
 */
function initTestimonialsCarousel() {
    const track = document.querySelector('.testimonials-track');
    const cards = document.querySelectorAll('.testimonial-card');
    const prevBtn = document.querySelector('.testimonial-prev');
    const nextBtn = document.querySelector('.testimonial-next');
    const dotsContainer = document.querySelector('.testimonials-dots');
    
    if (!track || cards.length === 0) return;

    let currentIndex = 0;
    let autoPlayInterval;

    // Create dots
    cards.forEach((_, index) => {
        const dot = document.createElement('button');
        dot.classList.add('testimonials-dot');
        dot.setAttribute('aria-label', `Go to testimonial ${index + 1}`);
        if (index === 0) dot.classList.add('active');
        dot.addEventListener('click', () => goToSlide(index));
        dotsContainer.appendChild(dot);
    });

    const dots = document.querySelectorAll('.testimonials-dot');

    function updateCarousel() {
        const cardWidth = cards[0].offsetWidth + 32; // Including gap
        track.style.transform = `translateX(-${currentIndex * cardWidth}px)`;
        
        dots.forEach((dot, index) => {
            dot.classList.toggle('active', index === currentIndex);
        });

        cards.forEach((card, index) => {
            card.classList.toggle('active', index === currentIndex);
        });
    }

    function goToSlide(index) {
        currentIndex = index;
        if (currentIndex < 0) currentIndex = cards.length - 1;
        if (currentIndex >= cards.length) currentIndex = 0;
        updateCarousel();
    }

    function nextSlide() {
        goToSlide(currentIndex + 1);
    }

    function prevSlide() {
        goToSlide(currentIndex - 1);
    }

    function startAutoPlay() {
        autoPlayInterval = setInterval(nextSlide, 5000);
    }

    function stopAutoPlay() {
        clearInterval(autoPlayInterval);
    }

    // Event listeners
    if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); stopAutoPlay(); startAutoPlay(); });
    if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); stopAutoPlay(); startAutoPlay(); });

    // Pause on hover
    const carousel = document.querySelector('.testimonials-carousel');
    if (carousel) {
        carousel.addEventListener('mouseenter', stopAutoPlay);
        carousel.addEventListener('mouseleave', startAutoPlay);
    }

    // Touch support
    let touchStartX = 0;
    let touchEndX = 0;

    track.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
        stopAutoPlay();
    }, { passive: true });

    track.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
        startAutoPlay();
    }, { passive: true });

    function handleSwipe() {
        const swipeThreshold = 50;
        const diff = touchStartX - touchEndX;
        
        if (Math.abs(diff) > swipeThreshold) {
            if (diff > 0) {
                nextSlide();
            } else {
                prevSlide();
            }
        }
    }

    // Initialize
    updateCarousel();
    startAutoPlay();

    // Handle resize
    window.addEventListener('resize', updateCarousel);
}

/**
 * Initialize Smooth Scroll for anchor links
 */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                e.preventDefault();
                const headerOffset = 80;
                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Initialize Scroll to Top Button
 */
function initScrollTopButton() {
    const scrollTopBtn = document.createElement('button');
    scrollTopBtn.className = 'scroll-top';
    scrollTopBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
    scrollTopBtn.setAttribute('aria-label', 'Scroll to top');
    document.body.appendChild(scrollTopBtn);

    window.addEventListener('scroll', () => {
        if (window.scrollY > 500) {
            scrollTopBtn.classList.add('visible');
        } else {
            scrollTopBtn.classList.remove('visible');
        }
    });

    scrollTopBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

/**
 * Initialize Header Shadow on Scroll
 */
function initHeaderShadow() {
    const header = document.querySelector('.header');
    if (!header) return;

    let lastScroll = 0;

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        if (currentScroll > 100) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }

        lastScroll = currentScroll;
    });
}

/**
 * Initialize Project Filtering
 */
function initProjectFilters() {
    const filterButtons = document.querySelectorAll('.filter-btn');
    const projectCards = document.querySelectorAll('.project-card');

    if (filterButtons.length === 0 || projectCards.length === 0) return;

    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Update active button
            filterButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            const filter = button.getAttribute('data-filter');

            // Filter projects
            projectCards.forEach(card => {
                const category = card.getAttribute('data-category');
                
                if (filter === 'all' || category === filter) {
                    card.style.display = 'block';
                    card.style.animation = 'fadeInUp 0.5s ease forwards';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}

/**
 * Initialize Blog Category Filtering
 */
function initBlogFilters() {
    const categoryButtons = document.querySelectorAll('.category-btn');
    const blogCards = document.querySelectorAll('.blog-card');

    if (categoryButtons.length === 0 || blogCards.length === 0) return;

    categoryButtons.forEach(button => {
        button.addEventListener('click', () => {
            categoryButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            const category = button.getAttribute('data-category');

            blogCards.forEach(card => {
                const cardCategory = card.getAttribute('data-category');
                
                if (category === 'all' || cardCategory === category) {
                    card.style.display = 'block';
                    card.style.animation = 'fadeInUp 0.5s ease forwards';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}

/**
 * Initialize Product Navigation Sticky Behavior
 */
function initProductNav() {
    const productNav = document.querySelector('.product-nav');
    if (!productNav) return;

    const navOffset = productNav.offsetTop;
    const header = document.querySelector('.header');
    const headerHeight = header ? header.offsetHeight : 80;

    window.addEventListener('scroll', () => {
        if (window.pageYOffset > navOffset - headerHeight) {
            productNav.classList.add('sticky');;
            productNav.style.top = `${headerHeight}px`;
        } else {
            productNav.classList.remove('sticky');
            productNav.style.top = '0';
        }
    });

    // Smooth scroll to sections
    const navLinks = productNav.querySelectorAll('a');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            
            if (targetSection) {
                const offset = targetSection.offsetTop - headerHeight - productNav.offsetHeight - 20;
                window.scrollTo({
                    top: offset,
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Utility: Throttle function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Utility: Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

/**
 * Utility: Check if element is in viewport
 */
function isInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

// Initialize additional page-specific features
if (document.querySelector('.projects-gallery')) {
    initProjectFilters();
}

if (document.querySelector('.blog-grid-section')) {
    initBlogFilters();
}

if (document.querySelector('.product-nav')) {
    initProductNav();
}