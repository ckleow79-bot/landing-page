/**
 * Supabase Integration JavaScript File
 * B & K Group Website
 */

// Supabase configuration - Loaded from environment variables via window.ENV or inline config
// For development: values are injected from .env file
// For production: set window.ENV before loading this script, or replace values below
const SUPABASE_URL = (typeof window !== 'undefined' && window.ENV && window.ENV.SUPABASE_URL) 
    ? window.ENV.SUPABASE_URL 
    : 'https://uloodavzquardkeecrlx.supabase.co';
    
const SUPABASE_KEY = (typeof window !== 'undefined' && window.ENV && window.ENV.SUPABASE_KEY) 
    ? window.ENV.SUPABASE_KEY 
    : 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVsb29kYXZ6cXVhcmRrZWVjcmx4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5MTc3MjMsImV4cCI6MjA4ODQ5MzcyM30.VqUNZWMKcqLolTnFDlOP874871r6AQmIEVnihdrAtwk';

let supabaseClient = null;

/**
 * Validation Functions
 */
function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function validatePhone(phone) {
    if (!phone) return true; // Phone is optional
    const phoneRegex = /^[\d\s\-\+\(\)]{8,}$/;
    return phoneRegex.test(phone);
}

function validateRequired(value) {
    return value.trim().length > 0;
}

function showFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    
    // Remove existing error
    const existingError = field.parentElement.querySelector('.field-error');
    if (existingError) {
        existingError.remove();
    }
    
    // Add error styling
    field.classList.add('error');
    
    // Create error message
    const errorEl = document.createElement('span');
    errorEl.className = 'field-error';
    errorEl.textContent = message;
    errorEl.style.color = '#e53e3e';
    errorEl.style.fontSize = '0.875rem';
    errorEl.style.marginTop = '0.25rem';
    errorEl.style.display = 'block';
    
    field.parentElement.appendChild(errorEl);
    
    // Remove error on input
    field.addEventListener('input', function removeError() {
        field.classList.remove('error');
        const error = field.parentElement.querySelector('.field-error');
        if (error) error.remove();
        field.removeEventListener('input', removeError);
    }, { once: true });
}

function clearAllFieldErrors() {
    const errors = document.querySelectorAll('.field-error');
    errors.forEach(error => error.remove());
    
    const errorFields = document.querySelectorAll('.error');
    errorFields.forEach(field => field.classList.remove('error'));
}

/**
 * Initialize Supabase Client
 */
function initSupabase() {
    if (typeof supabase !== 'undefined' && SUPABASE_URL !== 'https://your-supabase-project.supabase.co') {
        supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
        window.supabaseClient = supabaseClient; // exposed for programmes.js
        console.log('Supabase initialized successfully');
        
        // Initialize forms after Supabase is ready
        initContactForm();
        initNewsletterForm();
        initInvestorForm();
    } else {
        console.warn('Supabase not configured or library not loaded');
    }
}

/**
 * Initialize Contact Form
 */
function initContactForm() {
    const form = document.getElementById('contact-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        const messageEl = document.getElementById('contact-message-status');
        
        // Clear previous errors
        clearAllFieldErrors();
        
        // Collect form data
        const name = form.querySelector('#contact-name').value.trim();
        const email = form.querySelector('#contact-email').value.trim();
        const company = form.querySelector('#contact-company').value.trim();
        const phone = form.querySelector('#contact-phone').value.trim();
        const industry = form.querySelector('#contact-industry').value;
        const message = form.querySelector('#contact-message').value.trim();
        
        // Validate form
        let isValid = true;
        
        if (!validateRequired(name)) {
            showFieldError('contact-name', 'Please enter your name');
            isValid = false;
        }
        
        if (!validateRequired(email)) {
            showFieldError('contact-email', 'Please enter your email address');
            isValid = false;
        } else if (!validateEmail(email)) {
            showFieldError('contact-email', 'Please enter a valid email address (e.g., name@example.com)');
            isValid = false;
        }
        
        if (phone && !validatePhone(phone)) {
            showFieldError('contact-phone', 'Please enter a valid phone number with at least 8 digits');
            isValid = false;
        }
        
        if (!validateRequired(message)) {
            showFieldError('contact-message', 'Please enter your message');
            isValid = false;
        }
        
        if (!isValid) {
            showFormMessage(messageEl, 'Please correct the errors above and try again.', 'error');
            return;
        }
        
        // Show loading state
        submitBtn.innerHTML = '<span class="loading"></span> Sending...';
        submitBtn.disabled = true;
        
        // Prepare form data with type
        const formData = {
            name: name,
            email: email,
            company: company || null,
            phone: phone || null,
            industry: industry || null,
            message: message,
            type: 'general',
            created_at: new Date().toISOString()
        };

        try {
            if (supabaseClient) {
                // Submit to Supabase
                const { data, error } = await supabaseClient
                    .from('contact_submissions')
                    .insert([formData]);

                if (error) {
                    if (error.code === '23505') {
                        throw new Error('duplicate');
                    } else if (error.code === '23514') {
                        throw new Error('constraint');
                    }
                    throw error;
                }
                
                showFormMessage(messageEl, `Thank you, ${name}! Your message has been received. Our team will contact you within 24-48 hours.`, 'success');
                form.reset();
                
                // Trigger success animation
                if (typeof showSuccessAnimation === 'function') {
                    showSuccessAnimation(form);
                }
            } else {
                // Fallback: Simulate submission for demo
                console.log('Form data (Supabase not configured):', formData);
                showFormMessage(messageEl, `Thank you, ${name}! Your message has been received. Our team will contact you within 24-48 hours.`, 'success');
                form.reset();
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            
            let errorMessage = 'Sorry, there was an error sending your message. Please try again later.';
            
            if (error.message === 'duplicate') {
                errorMessage = 'It looks like you\'ve already submitted this message. Please wait a moment before trying again.';
            } else if (error.message === 'constraint') {
                errorMessage = 'Some information you provided doesn\'t meet our requirements. Please check and try again.';
            } else if (!navigator.onLine) {
                errorMessage = 'You appear to be offline. Please check your internet connection and try again.';
            } else if (error.code) {
                errorMessage = `Server error (${error.code}): Please try again later or contact us directly at info@yourcompany.com`;
            }
            
            showFormMessage(messageEl, errorMessage, 'error');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
}

/**
 * Initialize Newsletter Form
 */
function initNewsletterForm() {
    const forms = document.querySelectorAll('#newsletter-form, #blog-newsletter-form');
    
    forms.forEach(form => {
        if (!form) return;
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            const emailInput = form.querySelector('input[type="email"]');
            const messageEl = form.querySelector('.form-message') || document.createElement('div');
            
            if (!form.querySelector('.form-message')) {
                messageEl.className = 'form-message';
                form.appendChild(messageEl);
            }
            
            // Show loading state
            submitBtn.innerHTML = '<span class="loading"></span> Subscribing...';
            submitBtn.disabled = true;
            
            const formData = {
                email: emailInput.value,
                created_at: new Date().toISOString(),
                status: 'active'
            };

            try {
                if (supabaseClient) {
                    // Check if email already exists
                    const { data: existing } = await supabaseClient
                        .from('newsletter_subscribers')
                        .select('email')
                        .eq('email', formData.email)
                        .single();

                    if (existing) {
                        showFormMessage(messageEl, 'You are already subscribed to our newsletter!', 'success');
                    } else {
                        // Insert new subscriber
                        const { error } = await supabaseClient
                            .from('newsletter_subscribers')
                            .insert([formData]);

                        if (error) throw error;
                        
                        showFormMessage(messageEl, 'Thank you for subscribing to our newsletter!', 'success');
                        form.reset();
                    }
                } else {
                    console.log('Newsletter subscription (Supabase not configured):', formData);
                    showFormMessage(messageEl, 'Thank you for subscribing to our newsletter!', 'success');
                    form.reset();
                }
            } catch (error) {
                console.error('Error subscribing:', error);
                showFormMessage(messageEl, 'Sorry, there was an error. Please try again.', 'error');
            } finally {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    });
}

/**
 * Initialize Investor Form
 */
function initInvestorForm() {
    const form = document.getElementById('investor-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        const messageEl = document.getElementById('investor-message-status');
        
        // Show loading state
        submitBtn.innerHTML = '<span class="loading"></span> Sending...';
        submitBtn.disabled = true;
        
        const formData = {
            name: form.querySelector('#investor-name').value,
            email: form.querySelector('#investor-email').value,
            organization: form.querySelector('#investor-organization').value,
            inquiry_type: form.querySelector('#investor-type').value,
            message: form.querySelector('#investor-message').value,
            created_at: new Date().toISOString()
        };

        try {
            if (supabaseClient) {
                const { data, error } = await supabaseClient
                    .from('contact_submissions')
                    .insert([{ ...formData, type: 'investor' }]);

                if (error) throw error;
                
                showFormMessage(messageEl, 'Thank you for your inquiry! Our investor relations team will respond shortly.', 'success');
                form.reset();
            } else {
                console.log('Investor form data (Supabase not configured):', formData);
                showFormMessage(messageEl, 'Thank you for your inquiry! Our investor relations team will respond shortly.', 'success');
                form.reset();
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            showFormMessage(messageEl, 'Sorry, there was an error. Please try again.', 'error');
        } finally {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    });
}

/**
 * Show Form Message
 */
function showFormMessage(element, message, type) {
    element.textContent = message;
    element.className = `form-message ${type}`;
    element.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}

/**
 * Save Chat Conversation
 */
async function saveChatConversation(visitorId, messages) {
    if (!supabaseClient) {
        console.log('Chat conversation (Supabase not configured):', { visitorId, messages });
        return;
    }

    try {
        const { error } = await supabaseClient
            .from('chat_conversations')
            .upsert({
                visitor_id: visitorId,
                messages: JSON.stringify(messages),
                updated_at: new Date().toISOString()
            }, {
                onConflict: 'visitor_id'
            });

        if (error) throw error;
    } catch (error) {
        console.error('Error saving chat:', error);
    }
}

/**
 * Get Chat Conversation
 */
async function getChatConversation(visitorId) {
    if (!supabaseClient) return null;

    try {
        const { data, error } = await supabaseClient
            .from('chat_conversations')
            .select('messages')
            .eq('visitor_id', visitorId)
            .single();

        if (error) throw error;
        
        return data ? JSON.parse(data.messages) : null;
    } catch (error) {
        console.error('Error retrieving chat:', error);
        return null;
    }
}

/**
 * Generate Unique Visitor ID
 */
function generateVisitorId() {
    return 'visitor_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

/**
 * Get or Create Visitor ID
 */
function getVisitorId() {
    let visitorId = localStorage.getItem('chat_visitor_id');
    if (!visitorId) {
        visitorId = generateVisitorId();
        localStorage.setItem('chat_visitor_id', visitorId);
    }
    return visitorId;
}

// Initialize Supabase when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Wait a moment for Supabase library to load
    setTimeout(initSupabase, 100);
});