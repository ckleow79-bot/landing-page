/**
 * Animations JavaScript File
 * B & K Group Website
 * Uses Anime.js for advanced animations
 */

// Initialize animations when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Wait for Anime.js to be available
    if (typeof anime !== 'undefined') {
        initHeroAnimations();
        initScrollTriggeredAnimations();
        initMicroInteractions();
    } else {
        // Retry after a short delay if anime.js hasn't loaded yet
        setTimeout(() => {
            if (typeof anime !== 'undefined') {
                initHeroAnimations();
                initScrollTriggeredAnimations();
                initMicroInteractions();
            }
        }, 100);
    }
});

/**
 * Initialize Hero Section Animations
 */
function initHeroAnimations() {
    // Animate company name text
    const companyName = document.getElementById('animated-company-name');
    if (companyName) {
        // Split text into individual characters
        const text = companyName.textContent;
        companyName.innerHTML = text.split('').map(char => 
            char === ' ' ? ' ' : `<span class="char">${char}</span>`
        ).join('');

        // Animate characters
        anime({
            targets: '.company-name .char',
            translateY: [100, 0],
            rotateX: [-90, 0],
            opacity: [0, 1],
            easing: 'easeOutExpo',
            duration: 1200,
            delay: anime.stagger(50),
            loop: false
        });
    }

    // Animate hero content
    anime({
        targets: '.hero-content',
        translateY: [60, 0],
        opacity: [0, 1],
        easing: 'easeOutExpo',
        duration: 1400,
        delay: 300
    });

    // Animate headline
    anime({
        targets: '.hero-headline',
        translateY: [40, 0],
        opacity: [0, 1],
        easing: 'easeOutExpo',
        duration: 1200,
        delay: 800
    });

    // Animate subheadline
    anime({
        targets: '.hero-subheadline',
        translateY: [30, 0],
        opacity: [0, 1],
        easing: 'easeOutExpo',
        duration: 1200,
        delay: 1000
    });

    // Animate CTA buttons
    anime({
        targets: '.hero-ctas .btn',
        translateY: [20, 0],
        opacity: [0, 1],
        easing: 'easeOutExpo',
        duration: 1000,
        delay: anime.stagger(150, {start: 1200})
    });

    // Background subtle parallax
    const heroBackground = document.querySelector('.hero-background');
    if (heroBackground) {
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const rate = scrolled * 0.3;
            heroBackground.style.transform = `translateY(${rate}px)`;
        });
    }
}

/**
 * Initialize Scroll-Triggered Animations
 */
function initScrollTriggeredAnimations() {
    // Section headers animation
    const sectionHeaders = document.querySelectorAll('.section-header');
    
    const headerObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                anime({
                    targets: entry.target.children,
                    translateY: [40, 0],
                    opacity: [0, 1],
                    easing: 'easeOutExpo',
                    duration: 1000,
                    delay: anime.stagger(150)
                });
                headerObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    sectionHeaders.forEach(header => headerObserver.observe(header));

    // Industries cards staggered animation
    const industriesSection = document.querySelector('.industries-grid');
    if (industriesSection) {
        const cardsObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    anime({
                        targets: '.industry-card',
                        translateY: [60, 0],
                        opacity: [0, 1],
                        easing: 'easeOutExpo',
                        duration: 1000,
                        delay: anime.stagger(150)
                    });
                    
                    // Animate icons separately
                    anime({
                        targets: '.industry-icon',
                        scale: [0, 1],
                        rotate: [-180, 0],
                        easing: 'easeOutElastic(1, .6)',
                        duration: 1200,
                        delay: anime.stagger(150, {start: 300})
                    });
                    
                    cardsObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        cardsObserver.observe(industriesSection);
    }

    // Timeline animation
    const timelineSection = document.querySelector('.solution-timeline');
    if (timelineSection) {
        const timelineObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Animate line
                    anime({
                        targets: '.timeline-line',
                        scaleY: [0, 1],
                        easing: 'easeInOutExpo',
                        duration: 1500
                    });

                    // Animate steps
                    anime({
                        targets: '.timeline-step',
                        translateX: [-50, 0],
                        opacity: [0, 1],
                        easing: 'easeOutExpo',
                        duration: 1000,
                        delay: anime.stagger(200, {start: 500})
                    });

                    // Animate step numbers
                    anime({
                        targets: '.step-number',
                        scale: [0, 1],
                        easing: 'easeOutElastic(1, .5)',
                        duration: 1000,
                        delay: anime.stagger(200, {start: 700})
                    });

                    timelineObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        timelineObserver.observe(timelineSection);
    }

    // Why Choose Us cards
    const whyChooseSection = document.querySelector('.differentiators-grid');
    if (whyChooseSection) {
        const differentiatorsObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    anime({
                        targets: '.differentiator-card',
                        translateY: [50, 0],
                        opacity: [0, 1],
                        easing: 'easeOutExpo',
                        duration: 800,
                        delay: anime.stagger(100)
                    });

                    // Animate icons with bounce
                    anime({
                        targets: '.differentiator-icon',
                        translateY: [-20, 0],
                        opacity: [0, 1],
                        easing: 'easeOutBounce',
                        duration: 1000,
                        delay: anime.stagger(100, {start: 200})
                    });

                    differentiatorsObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        differentiatorsObserver.observe(whyChooseSection);
    }

    // Featured Projects animation
    const projectsSection = document.querySelector('.projects-grid');
    if (projectsSection) {
        const projectsObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    anime({
                        targets: '.project-card',
                        translateY: [60, 0],
                        opacity: [0, 1],
                        easing: 'easeOutExpo',
                        duration: 1000,
                        delay: anime.stagger(200)
                    });

                    // Image scale animation
                    anime({
                        targets: '.project-image img',
                        scale: [1.2, 1],
                        opacity: [0, 1],
                        easing: 'easeOutExpo',
                        duration: 1200,
                        delay: anime.stagger(200)
                    });

                    projectsObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        projectsObserver.observe(projectsSection);
    }

    // Newsletter section
    const newsletterSection = document.querySelector('.newsletter');
    if (newsletterSection) {
        const newsletterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    anime({
                        targets: '.newsletter-content',
                        translateY: [40, 0],
                        opacity: [0, 1],
                        easing: 'easeOutExpo',
                        duration: 1000
                    });

                    // Form input animation
                    anime({
                        targets: '.newsletter-form input',
                        translateX: [-30, 0],
                        opacity: [0, 1],
                        easing: 'easeOutExpo',
                        duration: 800,
                        delay: 300
                    });

                    newsletterObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.3 });

        newsletterObserver.observe(newsletterSection);
    }
}

/**
 * Initialize Micro-Interactions
 */
function initMicroInteractions() {
    // Button hover effects
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('mouseenter', () => {
            anime({
                targets: btn,
                scale: 1.05,
                duration: 300,
                easing: 'easeOutExpo'
            });
        });

        btn.addEventListener('mouseleave', () => {
            anime({
                targets: btn,
                scale: 1,
                duration: 300,
                easing: 'easeOutExpo'
            });
        });
    });

    // Industry card hover
    const industryCards = document.querySelectorAll('.industry-card');
    industryCards.forEach(card => {
        const icon = card.querySelector('.industry-icon');
        
        card.addEventListener('mouseenter', () => {
            anime({
                targets: card,
                translateY: -10,
                duration: 400,
                easing: 'easeOutExpo'
            });

            if (icon) {
                anime({
                    targets: icon,
                    scale: 1.15,
                    rotate: '5deg',
                    backgroundColor: '#ed8936',
                    duration: 400,
                    easing: 'easeOutExpo'
                });
            }
        });

        card.addEventListener('mouseleave', () => {
            anime({
                targets: card,
                translateY: 0,
                duration: 400,
                easing: 'easeOutExpo'
            });

            if (icon) {
                anime({
                    targets: icon,
                    scale: 1,
                    rotate: '0deg',
                    backgroundColor: 'rgba(26, 54, 93, 0.1)',
                    duration: 400,
                    easing: 'easeOutExpo'
                });
            }
        });
    });

    // Project card hover
    const projectCards = document.querySelectorAll('.project-card');
    projectCards.forEach(card => {
        const img = card.querySelector('.project-image img');
        
        card.addEventListener('mouseenter', () => {
            anime({
                targets: card,
                translateY: -10,
                duration: 400,
                easing: 'easeOutExpo'
            });

            if (img) {
                anime({
                    targets: img,
                    scale: 1.1,
                    duration: 600,
                    easing: 'easeOutExpo'
                });
            }
        });

        card.addEventListener('mouseleave', () => {
            anime({
                targets: card,
                translateY: 0,
                duration: 400,
                easing: 'easeOutExpo'
            });

            if (img) {
                anime({
                    targets: img,
                    scale: 1,
                    duration: 600,
                    easing: 'easeOutExpo'
                });
            }
        });
    });

    // Input focus effects
    const inputs = document.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            anime({
                targets: input,
                translateY: -2,
                boxShadow: '0 4px 20px rgba(26, 54, 93, 0.15)',
                duration: 300,
                easing: 'easeOutExpo'
            });
        });

        input.addEventListener('blur', () => {
            anime({
                targets: input,
                translateY: 0,
                boxShadow: '0 0 0 rgba(26, 54, 93, 0)',
                duration: 300,
                easing: 'easeOutExpo'
            });
        });
    });

    // Navigation link hover
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('mouseenter', () => {
            anime({
                targets: link,
                translateY: -2,
                duration: 200,
                easing: 'easeOutExpo'
            });
        });

        link.addEventListener('mouseleave', () => {
            anime({
                targets: link,
                translateY: 0,
                duration: 200,
                easing: 'easeOutExpo'
            });
        });
    });

    // Testimonial card animation
    const testimonialCards = document.querySelectorAll('.testimonial-card');
    testimonialCards.forEach(card => {
        const stars = card.querySelectorAll('.testimonial-rating i');
        
        card.addEventListener('mouseenter', () => {
            anime({
                targets: card,
                scale: 1.02,
                duration: 400,
                easing: 'easeOutExpo'
            });

            // Animate stars
            anime({
                targets: stars,
                scale: [1, 1.3, 1],
                rotate: [0, 15, 0],
                duration: 600,
                delay: anime.stagger(50),
                easing: 'easeOutElastic(1, .5)'
            });
        });

        card.addEventListener('mouseleave', () => {
            anime({
                targets: card,
                scale: 1,
                duration: 400,
                easing: 'easeOutExpo'
            });
        });
    });

    // Footer social icons
    const socialIcons = document.querySelectorAll('.footer-social a');
    socialIcons.forEach(icon => {
        icon.addEventListener('mouseenter', () => {
            anime({
                targets: icon,
                scale: 1.1,
                translateY: -3,
                duration: 300,
                easing: 'easeOutExpo'
            });
        });

        icon.addEventListener('mouseleave', () => {
            anime({
                targets: icon,
                scale: 1,
                translateY: 0,
                duration: 300,
                easing: 'easeOutExpo'
            });
        });
    });
}

/**
 * Counter Animation for Statistics
 */
function animateCounter(element, target, duration = 2000) {
    const start = 0;
    const startTime = performance.now();

    function updateCounter(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = Math.floor(easeOutQuart * target);
        
        element.textContent = current.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(updateCounter);
        } else {
            element.textContent = target.toLocaleString();
        }
    }

    requestAnimationFrame(updateCounter);
}

/**
 * Parallax Effect
 */
function initParallax() {
    const parallaxElements = document.querySelectorAll('.parallax');
    
    window.addEventListener('scroll', () => {
        parallaxElements.forEach(element => {
            const speed = element.dataset.speed || 0.5;
            const rect = element.getBoundingClientRect();
            const scrolled = window.pageYOffset;
            
            if (rect.top < window.innerHeight && rect.bottom > 0) {
                const yPos = -(scrolled * speed);
                element.style.transform = `translateY(${yPos}px)`;
            }
        });
    });
}

/**
 * Success Animation
 */
function showSuccessAnimation(container) {
    const checkmark = document.createElement('div');
    checkmark.className = 'success-checkmark';
    checkmark.innerHTML = '<i class="fas fa-check"></i>';
    
    container.appendChild(checkmark);
    
    anime({
        targets: checkmark,
        scale: [0, 1],
        opacity: [0, 1],
        easing: 'easeOutElastic(1, .5)',
        duration: 800,
        complete: () => {
            setTimeout(() => {
                anime({
                    targets: checkmark,
                    opacity: 0,
                    scale: 0,
                    duration: 400,
                    easing: 'easeInExpo',
                    complete: () => checkmark.remove()
                });
            }, 2000);
        }
    });
}