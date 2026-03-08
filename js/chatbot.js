/**
 * Chatbot JavaScript File
 * End-of-Line Packaging Automation Company Landing Page
 */

// Chatbot state
let chatbotOpen = false;
let chatMessages = [];
let currentStep = 'welcome';
let visitorEmail = null;
let visitorName = null;

// Chat flow configuration
const chatFlow = {
    welcome: {
        message: "Hello! Welcome to [Your Company Name]. How can I help you today?",
        options: [
            { text: "Get a Quote", next: 'quote' },
            { text: "View Products", next: 'products' },
            { text: "Technical Support", next: 'support' },
            { text: "Schedule a Call", next: 'schedule' }
        ]
    },
    quote: {
        message: "I'd be happy to help you get a quote! What type of packaging automation are you interested in?",
        options: [
            { text: "Case Packers", next: 'quote_details' },
            { text: "Palletizers", next: 'quote_details' },
            { text: "Wrapping Machines", next: 'quote_details' },
            { text: "Complete Line", next: 'quote_details' },
            { text: "Custom Solution", next: 'quote_details' }
        ]
    },
    quote_details: {
        message: "Great choice! To provide you with an accurate quote, could you please share your email address? Our team will contact you within 24 hours.",
        input: 'email',
        next: 'quote_thanks'
    },
    quote_thanks: {
        message: "Thank you! We've received your request. Our sales team will reach out to you shortly at {email}. Is there anything else I can help you with?",
        options: [
            { text: "Ask Another Question", next: 'welcome' },
            { text: "No, thanks", next: 'goodbye' }
        ]
    },
    products: {
        message: "We offer a wide range of packaging automation solutions. Which category would you like to explore?",
        options: [
            { text: "Case Packers", url: 'products.html#case-packers' },
            { text: "Palletizers", url: 'products.html#palletizers' },
            { text: "Wrapping Machines", url: 'products.html#wrapping' },
            { text: "Conveying Systems", url: 'products.html#conveying' },
            { text: "Custom Solutions", url: 'products.html#custom' }
        ]
    },
    support: {
        message: "I can help connect you with our technical support team. Please describe the issue you're experiencing with your equipment.",
        input: 'text',
        next: 'support_thanks'
    },
    support_thanks: {
        message: "Thank you for providing those details. Our technical support team will review your issue and contact you within 4 hours during business hours (Mon-Fri, 8AM-6PM). For urgent issues, please call us at +60 XX-XXXX XXXX.",
        options: [
            { text: "Back to Main Menu", next: 'welcome' },
            { text: "Close Chat", next: 'goodbye' }
        ]
    },
    schedule: {
        message: "I'd be happy to schedule a call for you! Please provide your email address and preferred date/time, and we'll confirm the appointment.",
        input: 'text',
        next: 'schedule_thanks'
    },
    schedule_thanks: {
        message: "Perfect! We've received your scheduling request. Our team will send you a calendar invite within 24 hours. Looking forward to speaking with you!",
        options: [
            { text: "Back to Main Menu", next: 'welcome' },
            { text: "Close Chat", next: 'goodbye' }
        ]
    },
    goodbye: {
        message: "Thank you for chatting with us! If you have any more questions, feel free to reach out. Have a great day!",
        options: [
            { text: "Start Over", next: 'welcome' }
        ]
    }
};

/**
 * Initialize Chatbot
 */
function initChatbot() {
    const chatbotToggle = document.querySelector('.chatbot-toggle');
    const chatbotWindow = document.querySelector('.chatbot-window');
    const chatbotClose = document.querySelector('.chatbot-close');
    const chatInput = document.querySelector('.chatbot-input input');
    const chatSend = document.querySelector('.chatbot-send');

    if (!chatbotToggle || !chatbotWindow) return;

    // Load previous conversation
    loadChatHistory();

    // Toggle chatbot
    chatbotToggle.addEventListener('click', () => {
        toggleChatbot();
    });

    // Close chatbot
    if (chatbotClose) {
        chatbotClose.addEventListener('click', () => {
            closeChatbot();
        });
    }

    // Send message
    if (chatSend) {
        chatSend.addEventListener('click', () => {
            handleUserInput();
        });
    }

    // Send on Enter key
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleUserInput();
            }
        });
    }

    // Initialize with welcome message
    if (chatMessages.length === 0) {
        addBotMessage(chatFlow.welcome.message);
        addQuickReplies(chatFlow.welcome.options);
    } else {
        renderChatHistory();
    }
}

/**
 * Toggle Chatbot Window
 */
function toggleChatbot() {
    const chatbotWindow = document.querySelector('.chatbot-window');
    const chatbotToggle = document.querySelector('.chatbot-toggle');
    
    if (!chatbotWindow) return;

    chatbotOpen = !chatbotOpen;
    
    if (chatbotOpen) {
        chatbotWindow.classList.add('active');
        chatbotToggle.classList.add('hidden');
        
        // Focus input
        setTimeout(() => {
            const input = document.querySelector('.chatbot-input input');
            if (input) input.focus();
        }, 300);
    } else {
        closeChatbot();
    }
}

/**
 * Close Chatbot Window
 */
function closeChatbot() {
    const chatbotWindow = document.querySelector('.chatbot-window');
    const chatbotToggle = document.querySelector('.chatbot-toggle');
    
    if (!chatbotWindow) return;

    chatbotOpen = false;
    chatbotWindow.classList.remove('active');
    chatbotToggle.classList.remove('hidden');
}

/**
 * Add Bot Message
 */
function addBotMessage(message) {
    const messagesContainer = document.querySelector('.chatbot-messages');
    if (!messagesContainer) return;

    const messageEl = document.createElement('div');
    messageEl.className = 'chat-message bot-message';
    messageEl.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <p>${message}</p>
            <span class="message-time">${getCurrentTime()}</span>
        </div>
    `;
    
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
    
    // Save to history
    chatMessages.push({
        type: 'bot',
        message: message,
        time: new Date().toISOString()
    });
    
    saveChatHistory();
}

/**
 * Add User Message
 */
function addUserMessage(message) {
    const messagesContainer = document.querySelector('.chatbot-messages');
    if (!messagesContainer) return;

    const messageEl = document.createElement('div');
    messageEl.className = 'chat-message user-message';
    messageEl.innerHTML = `
        <div class="message-content">
            <p>${message}</p>
            <span class="message-time">${getCurrentTime()}</span>
        </div>
    `;
    
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
    
    // Save to history
    chatMessages.push({
        type: 'user',
        message: message,
        time: new Date().toISOString()
    });
    
    saveChatHistory();
}

/**
 * Add Quick Reply Buttons
 */
function addQuickReplies(options) {
    const messagesContainer = document.querySelector('.chatbot-messages');
    if (!messagesContainer || !options) return;

    const repliesEl = document.createElement('div');
    repliesEl.className = 'quick-replies';
    
    options.forEach(option => {
        const btn = document.createElement('button');
        btn.className = 'quick-reply-btn';
        btn.textContent = option.text;
        btn.addEventListener('click', () => {
            handleQuickReply(option);
        });
        repliesEl.appendChild(btn);
    });
    
    messagesContainer.appendChild(repliesEl);
    scrollToBottom();
}

/**
 * Handle Quick Reply
 */
function handleQuickReply(option) {
    // Add user message
    addUserMessage(option.text);
    
    // Remove quick replies
    const quickReplies = document.querySelector('.quick-replies');
    if (quickReplies) {
        quickReplies.remove();
    }
    
    // Show typing indicator
    showTypingIndicator();
    
    setTimeout(() => {
        hideTypingIndicator();
        
        if (option.url) {
            // If URL provided, redirect
            addBotMessage(`I'll take you to our ${option.text} page.`);
            setTimeout(() => {
                window.open(option.url, '_blank');
            }, 1000);
        } else if (option.next) {
            // Move to next step in flow
            currentStep = option.next;
            const step = chatFlow[currentStep];
            
            if (step) {
                // Replace email placeholder if exists
                let message = step.message;
                if (visitorEmail && message.includes('{email}')) {
                    message = message.replace('{email}', visitorEmail);
                }
                
                addBotMessage(message);
                
                if (step.options) {
                    addQuickReplies(step.options);
                }
                
                // Show input field if needed
                const input = document.querySelector('.chatbot-input input');
                if (step.input) {
                    input.placeholder = step.input === 'email' ? 'Enter your email...' : 'Type your message...';
                }
            }
        }
    }, 1000);
}

/**
 * Handle User Input
 */
function handleUserInput() {
    const input = document.querySelector('.chatbot-input input');
    if (!input) return;
    
    const message = input.value.trim();
    if (!message) return;
    
    // Add user message
    addUserMessage(message);
    input.value = '';
    
    // Show typing indicator
    showTypingIndicator();
    
    setTimeout(() => {
        hideTypingIndicator();
        
        // Process input based on current step
        const step = chatFlow[currentStep];
        
        if (step && step.input) {
            if (step.input === 'email') {
                if (validateEmail(message)) {
                    visitorEmail = message;
                    
                    // Save email for offline contact
                    if (typeof supabaseClient !== 'undefined') {
                        saveOfflineContact(visitorEmail, 'chat_quote_request');
                    }
                } else {
                    addBotMessage("That doesn't appear to be a valid email address. Please try again.");
                    return;
                }
            }
            
            // Move to next step
            if (step.next) {
                currentStep = step.next;
                const nextStep = chatFlow[currentStep];
                
                if (nextStep) {
                    let responseMessage = nextStep.message;
                    if (visitorEmail && responseMessage.includes('{email}')) {
                        responseMessage = responseMessage.replace('{email}', visitorEmail);
                    }
                    
                    addBotMessage(responseMessage);
                    
                    if (nextStep.options) {
                        addQuickReplies(nextStep.options);
                    }
                }
            }
        } else {
            // Handle general conversation
            handleGeneralQuery(message);
        }
    }, 1000);
}

/**
 * Handle General Query
 */
function handleGeneralQuery(message) {
    const lowerMessage = message.toLowerCase();
    
    if (lowerMessage.includes('price') || lowerMessage.includes('cost') || lowerMessage.includes('quote')) {
        addBotMessage("I'd be happy to help you with pricing information. Let me connect you with our sales team.");
        currentStep = 'quote';
        addQuickReplies(chatFlow.quote.options);
    } else if (lowerMessage.includes('product') || lowerMessage.includes('machine')) {
        addBotMessage("We offer various packaging automation solutions. Which type are you interested in?");
        currentStep = 'products';
        addQuickReplies(chatFlow.products.options);
    } else if (lowerMessage.includes('support') || lowerMessage.includes('help') || lowerMessage.includes('problem')) {
        addBotMessage("I understand you need technical support. Let me help you with that.");
        currentStep = 'support';
        addBotMessage(chatFlow.support.message);
    } else if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hey')) {
        addBotMessage("Hello! How can I assist you today?");
        addQuickReplies(chatFlow.welcome.options);
    } else if (lowerMessage.includes('bye') || lowerMessage.includes('goodbye') || lowerMessage.includes('thanks')) {
        addBotMessage(chatFlow.goodbye.message);
        addQuickReplies(chatFlow.goodbye.options);
    } else {
        addBotMessage("I'm not sure I understand. Here are some things I can help you with:");
        addQuickReplies(chatFlow.welcome.options);
    }
}

/**
 * Show Typing Indicator
 */
function showTypingIndicator() {
    const messagesContainer = document.querySelector('.chatbot-messages');
    if (!messagesContainer) return;

    const typingEl = document.createElement('div');
    typingEl.className = 'chat-message bot-message typing';
    typingEl.id = 'typing-indicator';
    typingEl.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    
    messagesContainer.appendChild(typingEl);
    scrollToBottom();
}

/**
 * Hide Typing Indicator
 */
function hideTypingIndicator() {
    const typingEl = document.getElementById('typing-indicator');
    if (typingEl) {
        typingEl.remove();
    }
}

/**
 * Scroll to Bottom of Chat
 */
function scrollToBottom() {
    const messagesContainer = document.querySelector('.chatbot-messages');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

/**
 * Get Current Time
 */
function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: true 
    });
}

/**
 * Validate Email
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Save Chat History
 */
function saveChatHistory() {
    const visitorId = typeof getVisitorId === 'function' ? getVisitorId() : 'guest_' + Date.now();
    const chatData = {
        messages: chatMessages,
        currentStep: currentStep,
        visitorEmail: visitorEmail,
        lastUpdated: new Date().toISOString()
    };
    
    localStorage.setItem('chat_history_' + visitorId, JSON.stringify(chatData));
    
    // Also save to Supabase if available
    if (typeof saveChatConversation === 'function') {
        saveChatConversation(visitorId, chatData);
    }
}

/**
 * Load Chat History
 */
function loadChatHistory() {
    const visitorId = typeof getVisitorId === 'function' ? getVisitorId() : null;
    if (!visitorId) return;
    
    const saved = localStorage.getItem('chat_history_' + visitorId);
    if (saved) {
        const chatData = JSON.parse(saved);
        chatMessages = chatData.messages || [];
        currentStep = chatData.currentStep || 'welcome';
        visitorEmail = chatData.visitorEmail || null;
    }
}

/**
 * Render Chat History
 */
function renderChatHistory() {
    const messagesContainer = document.querySelector('.chatbot-messages');
    if (!messagesContainer) return;
    
    messagesContainer.innerHTML = '';
    
    chatMessages.forEach(msg => {
        if (msg.type === 'bot') {
            const messageEl = document.createElement('div');
            messageEl.className = 'chat-message bot-message';
            messageEl.innerHTML = `
                <div class="message-avatar">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="message-content">
                    <p>${msg.message}</p>
                    <span class="message-time">${formatTime(msg.time)}</span>
                </div>
            `;
            messagesContainer.appendChild(messageEl);
        } else {
            const messageEl = document.createElement('div');
            messageEl.className = 'chat-message user-message';
            messageEl.innerHTML = `
                <div class="message-content">
                    <p>${msg.message}</p>
                    <span class="message-time">${formatTime(msg.time)}</span>
                </div>
            `;
            messagesContainer.appendChild(messageEl);
        }
    });
    
    // Add current step options
    const step = chatFlow[currentStep];
    if (step && step.options) {
        addQuickReplies(step.options);
    }
    
    scrollToBottom();
}

/**
 * Format Time from ISO String
 */
function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: true 
    });
}

/**
 * Save Offline Contact
 */
async function saveOfflineContact(email, type) {
    if (typeof supabaseClient !== 'undefined' && supabaseClient) {
        try {
            await supabaseClient
                .from('chat_conversations')
                .upsert({
                    visitor_id: typeof getVisitorId === 'function' ? getVisitorId() : 'guest',
                    email: email,
                    type: type,
                    created_at: new Date().toISOString()
                });
        } catch (error) {
            console.error('Error saving offline contact:', error);
        }
    }
}

// Auto-open chatbot after 30 seconds if first visit
setTimeout(() => {
    const hasVisited = localStorage.getItem('chat_has_visited');
    if (!hasVisited && !chatbotOpen) {
        localStorage.setItem('chat_has_visited', 'true');
        const chatbotToggle = document.querySelector('.chatbot-toggle');
        if (chatbotToggle) {
            chatbotToggle.classList.add('pulse');
            setTimeout(() => {
                chatbotToggle.classList.remove('pulse');
            }, 5000);
        }
    }
}, 30000);