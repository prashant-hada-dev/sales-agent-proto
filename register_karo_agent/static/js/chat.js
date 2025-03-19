document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatWidget = document.getElementById('chat-widget');
    const chatBubble = document.getElementById('chat-bubble');
    const closeChat = document.getElementById('close-chat');
    const minimizeChat = document.getElementById('minimize-chat');
    const maximizeChat = document.getElementById('maximize-chat'); // New maximize button
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendMessage = document.getElementById('send-message');
    const openChat = document.getElementById('open-chat');
    const serviceChatButtons = document.querySelectorAll('.chat-service');
    const pricingChatButtons = document.querySelectorAll('.chat-pricing');
    const documentUploadArea = document.getElementById('document-upload-area');
    const documentUploadForm = document.getElementById('document-upload-form');
    const fileInput = document.getElementById('document-file');
    const fileName = document.getElementById('file-name');
    const paymentArea = document.getElementById('payment-area');
    const paymentLink = document.getElementById('payment-link');
    const chatHeader = document.getElementById('chat-header');
    const chatContainer = document.getElementById('chat-container');

    // Add debugging indicator
    const debugInfo = document.createElement('div');
    debugInfo.id = 'debug-info';
    debugInfo.style.position = 'fixed';
    debugInfo.style.bottom = '10px';
    debugInfo.style.right = '10px';
    debugInfo.style.backgroundColor = 'rgba(0,0,0,0.7)';
    debugInfo.style.color = 'white';
    debugInfo.style.padding = '5px 10px';
    debugInfo.style.borderRadius = '5px';
    debugInfo.style.fontSize = '12px';
    debugInfo.style.zIndex = '10000';
    debugInfo.innerHTML = 'Debug: Initializing...';
    document.body.appendChild(debugInfo);

    function updateDebug(message) {
        console.log(`DEBUG: ${message}`);
        debugInfo.innerHTML = `Debug: ${message}`;
    }

    // Variables
    let sessionId = null;
    let serverSessionId = null; // Store the server's assigned session ID
    let cookieId = null; // Store the cookie ID for user tracking
    let socket = null;
    let typingTimer = null;
    let inactivityTimer = null;
    let retryCount = 0;
    let followUpCount = 0;
    let minimized = false;
    let maximized = false; // Track maximized state
    const maxRetries = 3;
    const maxFollowUps = 5; // Maximum number of follow-ups before backing off
    const baseInactivityTimeout = 120000; // 2 minutes initial timeout
    const reconnectInterval = 3000; // 3 seconds
    const cookieLifetime = 365; // Cookie lifetime in days (1 year)
    
    // Progressive timeouts that increase with each follow-up
    const inactivityTimeouts = [
        120000, // 2 minutes for first follow-up
        180000, // 3 minutes for second follow-up
        300000, // 5 minutes for third follow-up
        600000, // 10 minutes for fourth follow-up
        900000  // 15 minutes for fifth and subsequent follow-ups
    ];

    // Helper Functions
    function formatTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function addMessage(text, sender, type = 'message') {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        
        if (sender === 'user') {
            messageDiv.classList.add('user-message');
        } else {
            if (type === 'follow_up') {
                messageDiv.classList.add('follow-up-message');
            } else {
                messageDiv.classList.add('bot-message');
            }
        }
        
        // Process links in messages
        const processedText = text.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');
        
        messageDiv.innerHTML = `
            ${processedText}
            <div class="message-time">${formatTime()}</div>
        `;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function connectWebSocket() {
        if (socket && socket.readyState === WebSocket.OPEN) {
            updateDebug('WebSocket already connected');
            return;
        }

        // Get the correct WebSocket URL based on the current location
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        updateDebug(`Connecting to WebSocket at ${wsUrl}`);
        
        socket = new WebSocket(wsUrl);
        
        socket.onopen = function() {
            updateDebug('WebSocket connected successfully!');
            retryCount = 0;
            
            // Get device info for tracking
            const deviceInfo = getDeviceInfo();
            
            // Send cookie ID if we have one
            if (cookieId) {
                socket.send(JSON.stringify({
                    type: 'cookie_id',
                    cookie_id: cookieId
                }));
                updateDebug(`Sent cookie ID: ${cookieId}`);
            }
            
            // If we have a session ID from a previous connection, include it
            if (sessionId) {
                const reconnectMsg = {
                    type: 'message',
                    text: 'Reconnected to chat',
                    previous_session_id: sessionId,
                    device_info: deviceInfo
                };
                
                // Include cookie ID if available
                if (cookieId) {
                    reconnectMsg.cookie_id = cookieId;
                }
                
                socket.send(JSON.stringify(reconnectMsg));
                updateDebug(`Sent reconnection message with session ID: ${sessionId}`);
            } else {
                // For new sessions, we'll just wait for the server to assign us a session ID
                // and then we'll update our tracking info with the next message
                
                // Send client info to help server identify returning users
                const clientInfo = {
                    device: deviceInfo
                };
                
                // Send additional user info if available (from localStorage)
                let userInfo;
                try {
                    userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
                    if (userInfo.name) clientInfo.name = userInfo.name;
                    if (userInfo.email) clientInfo.email = userInfo.email;
                    if (userInfo.phone) clientInfo.phone = userInfo.phone;
                } catch (e) {
                    console.error('Error parsing user info:', e);
                }
                
                socket.send(JSON.stringify({
                    type: 'client_info',
                    client_info: clientInfo,
                    cookie_id: cookieId
                }));
                
                // Send initial greeting on first connection
                setTimeout(() => {
                    const botGreeting = "👋 Hello! I'm your RegisterKaro incorporation specialist. I can help you register your company quickly and efficiently. How can I assist you today?";
                    addMessage(botGreeting, 'bot');
                    updateDebug('Added initial greeting');
                }, 500);
            }
        };
        
        socket.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                updateDebug(`Received message of type: ${data.type}`);
                
                if (data.type === 'session_info') {
                    // Store the server's session ID
                    serverSessionId = data.session_id;
                    updateDebug(`Received server session ID: ${serverSessionId}`);
                    
                    // Check if the server needs us to send a cookie
                    if (data.requires_cookie) {
                        // Send cookie ID if we have one, otherwise tell server we don't have one
                        socket.send(JSON.stringify({
                            type: 'cookie_id',
                            cookie_id: cookieId || ''
                        }));
                        updateDebug(`Sent cookie_id response: ${cookieId || '(none)'}`);
                    }
                } else if (data.type === 'set_cookie') {
                    // Server is asking us to set a new cookie
                    cookieId = data.cookie_id;
                    setCookie('registerKaroCookieId', cookieId, cookieLifetime);
                    updateDebug(`Set new cookie ID: ${cookieId}`);
                    
                    // Also store in user info for redundancy
                    let userInfo;
                    try {
                        userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
                        userInfo.cookieId = cookieId;
                        localStorage.setItem('userInfo', JSON.stringify(userInfo));
                    } catch (e) {
                        console.error('Error updating user info with cookie:', e);
                    }
                } else if (data.type === 'message' || data.type === 'follow_up') {
                    updateDebug(`Adding message to chat: ${data.text.substring(0, 30)}...`);
                    addMessage(data.text, 'bot', data.type);
                    resetFollowUpCount();
                    
                    // Auto-close payment area if payment confirmation message is received
                    if (data.type === 'message' && 
                        (data.text.includes("payment has been successfully received") || 
                         data.text.includes("Payment successful") || 
                         data.text.includes("payment confirmed"))) {
                        closePaymentArea();
                    }
                } else if (data.type === 'show_document_upload') {
                    showDocumentUploadForm();
                    updateDebug('Showing document upload form');
                } else if (data.type === 'payment_link') {
                    showPaymentLink(data.link);
                    updateDebug(`Showing payment link: ${data.link}`);
                }
            } catch (error) {
                updateDebug(`Error parsing WebSocket message: ${error.message}`);
                console.error('Error parsing WebSocket message:', error);
                console.error('Raw message data:', event.data);
            }
        };
        
        socket.onclose = function(event) {
            updateDebug(`WebSocket closed with code ${event.code}, reason: ${event.reason}`);
            
            // Try to reconnect with exponential backoff
            if (retryCount < maxRetries) {
                const timeout = Math.min(30000, reconnectInterval * Math.pow(2, retryCount));
                updateDebug(`Attempting to reconnect in ${timeout/1000} seconds...`);
                
                setTimeout(() => {
                    retryCount++;
                    connectWebSocket();
                }, timeout);
            } else {
                updateDebug('Failed to reconnect after several attempts');
                addMessage('Connection lost. Please reload the page to continue chatting.', 'bot');
            }
        };
        
        socket.onerror = function(error) {
            updateDebug(`WebSocket error: ${error.message || 'Unknown error'}`);
            console.error('WebSocket error:', error);
        };
    }

    function sendMessageToServer(text) {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            updateDebug('WebSocket not connected, attempting to reconnect...');
            addMessage('Connection lost. Trying to reconnect...', 'bot');
            connectWebSocket();
            return;
        }
        
        // Get device info for tracking across sessions
        const deviceInfo = getDeviceInfo();
        
        const message = {
            type: 'message',
            text: text,
            device_info: deviceInfo
        };
        
        // Add session ID if we have one
        if (serverSessionId) {
            message.session_id = serverSessionId;
        } else if (sessionId) {
            message.previous_session_id = sessionId;
        }
        
        // Add cookie ID if we have one
        if (cookieId) {
            message.cookie_id = cookieId;
        }
        
        updateDebug(`Sending message to server: ${text.substring(0, 30)}...`);
        socket.send(JSON.stringify(message));
        updateDebug('Message sent successfully');
    }

    function resetInactivityTimer() {
        clearTimeout(inactivityTimer);
        
        // Only set a new timer if we haven't reached max follow-ups
        if (followUpCount < maxFollowUps) {
            // Get the appropriate timeout based on follow-up count
            const timeout = inactivityTimeouts[Math.min(followUpCount, inactivityTimeouts.length - 1)];
            
            updateDebug(`Setting inactivity timer: ${timeout/1000} seconds (follow-up #${followUpCount + 1})`);
            
            inactivityTimer = setTimeout(() => {
                if (socket && socket.readyState === WebSocket.OPEN && serverSessionId) {
                    updateDebug(`User inactive for ${timeout/1000} seconds, sending follow-up #${followUpCount + 1}`);
                    
                    // Check if payment area is visible to determine context
                    let context = null;
                    if (paymentArea.style.display === 'block') {
                        context = 'payment_pending';
                    }
                    
                    // Include follow-up count in the message to help server tailor response
                    const inactiveMsg = {
                        type: 'inactive',
                        session_id: serverSessionId,
                        context: context,
                        follow_up_count: followUpCount
                    };
                    
                    // Include cookie ID if we have one
                    if (cookieId) {
                        inactiveMsg.cookie_id = cookieId;
                    }
                    
                    socket.send(JSON.stringify(inactiveMsg));
                    
                    // Increment follow-up count for next time
                    followUpCount++;
                }
            }, timeout);
        } else {
            updateDebug(`Maximum follow-ups (${maxFollowUps}) reached. No more follow-ups will be sent.`);
        }
    }
    
    // Reset follow-up count when user interacts
    function resetFollowUpCount() {
        if (followUpCount > 0) {
            updateDebug(`Resetting follow-up count from ${followUpCount} to 0 due to user activity`);
            followUpCount = 0;
        }
        resetInactivityTimer();
    }

    function showDocumentUploadForm() {
        documentUploadArea.style.display = 'block';
        // Ensure the chat window is adjusted to keep both visible
        adjustChatLayout();
    }

    function showPaymentLink(link) {
        // Sanitize and log the link
        link = link ? link.trim() : '';
        updateDebug(`Raw payment link received: ${link}`);
        
        // Extract the payment ID from the link URL or use the link directly
        let paymentId = '';
        if (link.includes('/')) {
            paymentId = link.split('/').pop();
        } else {
            paymentId = link;
        }
        
        updateDebug(`Payment ID before sanitization: ${paymentId}`);
        
        // Create a safe payment ID for both display and API usage
        // We keep only allowed characters for URLs and IDs
        const safePaymentId = paymentId.replace(/[^a-zA-Z0-9_-]/g, '');
        
        updateDebug(`Sanitized payment ID: ${safePaymentId}`);
        
        // Store the payment ID and link for later use
        paymentLink.dataset.paymentId = safePaymentId;
        paymentLink.dataset.originalLink = link;
        paymentLink.href = "#"; // Use # to prevent navigation, we'll handle in click event
        
        // Display the payment area
        paymentArea.style.display = 'block';
        
        // Add close button if it doesn't exist
        if (!document.querySelector('.payment-close')) {
            const closeButton = document.createElement('button');
            closeButton.classList.add('payment-close');
            closeButton.innerHTML = '&times;';
            closeButton.addEventListener('click', closePaymentArea);
            paymentArea.appendChild(closeButton);
        }
        
        // Ensure the chat window is adjusted to keep both visible
        adjustChatLayout();
    }
    
    function closePaymentArea() {
        paymentArea.style.display = 'none';
        // Readjust chat layout
        adjustChatLayout();
    }
    
    function adjustChatLayout() {
        // Determine if any special areas are showing
        const documentShowing = (documentUploadArea.style.display === 'block');
        const paymentShowing = (paymentArea.style.display === 'block');
        
        // Add appropriate classes to ensure chat messages remain visible
        if (documentShowing || paymentShowing) {
            chatMessages.classList.add('with-overlay');
        } else {
            chatMessages.classList.remove('with-overlay');
        }
        
        // Scroll to the bottom to ensure latest messages are visible
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Initialize Razorpay checkout with dynamic payment details
    async function openRazorpayCheckout(paymentId) {
        // Add a message showing that payment is being initialized
        addMessage("Opening secure payment gateway...", 'bot');
        
        // Check if Razorpay is available
        if (typeof Razorpay === 'undefined') {
            updateDebug("Razorpay SDK not loaded");
            addMessage("Our payment system is currently loading. Please try again in a few seconds.", 'bot');
            
            // Try to load Razorpay dynamically
            const script = document.createElement('script');
            script.src = 'https://checkout.razorpay.com/v1/checkout.js';
            script.async = true;
            script.onload = function() {
                updateDebug("Razorpay SDK loaded dynamically");
                // Try again after loading
                setTimeout(() => openRazorpayCheckout(paymentId), 1000);
            };
            script.onerror = function() {
                updateDebug("Failed to load Razorpay SDK dynamically");
                addMessage("There was an issue loading our payment system. Please try again or contact support.", 'bot');
            };
            document.head.appendChild(script);
            return;
        }
        
        updateDebug(`Starting Razorpay checkout for payment ID: ${paymentId}`);
        
        try {
            // Encode the payment ID to make it URL-safe
            const encodedPaymentId = encodeURIComponent(paymentId);
            updateDebug(`Using encoded payment ID: ${encodedPaymentId}`);
            
            // Fetch payment details from server
            const currentSessionId = serverSessionId || sessionId;
            let url = `/payment-details/${encodedPaymentId}?session_id=${encodeURIComponent(currentSessionId)}`;
            
            // Add cookie ID if available
            if (cookieId) {
                url += `&cookie_id=${encodeURIComponent(cookieId)}`;
            }
            
            updateDebug(`Fetching payment details from: ${url}`);
            
            let amount, description, currency;
            
            try {
                const response = await fetch(url);
                
                if (!response.ok) {
                    updateDebug(`Server error: ${response.status} ${response.statusText}`);
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }
                
                const paymentDetails = await response.json();
                updateDebug(`Payment details received: ${JSON.stringify(paymentDetails)}`);
                
                // Get proper amount from payment details or use default
                // Ensure amount is in paise (Razorpay expects amount in paise)
                // If amount is already in paise (>1000), use it directly, otherwise multiply by 100
                amount = paymentDetails?.amount || 500000; // Default to ₹5,000 in paise if not available
                
                // Razorpay expects amount in paise (1 rupee = 100 paise)
                // Convert to paise if not already (assume below 10,000 is rupees)
                if (amount < 10000) {
                    amount = amount * 100;
                    updateDebug(`Converting amount from rupees to paise: ₹${amount/100} (${amount} paise)`);
                }
                
                description = paymentDetails?.description || 'Company Registration';
                currency = paymentDetails?.currency || 'INR';
                
                updateDebug(`Configuring Razorpay with amount: ${amount} paise (₹${amount/100})`);
            } catch (error) {
                updateDebug(`Error fetching payment details: ${error.message}`);
                addMessage("There was an issue retrieving payment details. Please try again or contact support.", 'bot');
                return; // Exit the function on error
            }
            
            // Use the Razorpay test key
            const razorpayKey = 'rzp_test_I98HfDwdi2qQ3T';
            
            // Configure Razorpay options with dynamic details
            const options = {
                key: razorpayKey,
                amount: amount,
                currency: currency,
                name: 'RegisterKaro',
                description: description,
                image: 'https://ui-avatars.com/api/?name=RegisterKaro&background=0047ab&color=fff',
                order_id: '', // Leave blank for our simulated environment
                handler: function (response) {
                    // Payment successful
                    addMessage("Payment successful! Your transaction ID is: " + response.razorpay_payment_id, 'user');
                    
                    // Check payment status on server
                    checkPaymentStatus(paymentId);
                    
                    // Close the payment area
                    closePaymentArea();
                },
                prefill: {
                    name: 'Test User',
                    email: 'test@example.com',
                    contact: '9999999999'
                },
                notes: {
                    payment_id: paymentId
                },
                theme: {
                    color: '#0047AB'
                },
                modal: {
                    ondismiss: function() {
                        addMessage("I'll complete the payment later.", 'user');
                    }
                },
                // Enable all payment methods
                // No specific config means all payment options are shown
            };
            
            // Create and open Razorpay checkout
            const razorpayCheckout = new Razorpay(options);
            razorpayCheckout.open();
            
        } catch (error) {
            updateDebug(`Error initializing payment: ${error.message}`);
            console.error('Error initializing payment:', error);
            addMessage("There was an issue initializing payment. Please try again or contact support.", 'bot');
        }
    }

    // Event Listeners
    chatBubble.addEventListener('click', function() {
        chatWidget.style.display = 'flex';
        chatBubble.style.display = 'none';
        
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
        
        resetFollowUpCount();
        messageInput.focus();
    });

    closeChat.addEventListener('click', function() {
        chatWidget.style.display = 'none';
        chatBubble.style.display = 'flex';
        clearTimeout(inactivityTimer);
    });

    openChat.addEventListener('click', function() {
        chatWidget.style.display = 'flex';
        chatBubble.style.display = 'none';
        
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
        
        resetFollowUpCount();
        messageInput.focus();
    });

    serviceChatButtons.forEach(button => {
        button.addEventListener('click', function() {
            const service = this.getAttribute('data-service');
            
            chatWidget.style.display = 'flex';
            chatBubble.style.display = 'none';
            
            if (!socket || socket.readyState !== WebSocket.OPEN) {
                connectWebSocket();
            }
            
            // Add a slight delay so the greeting appears first
            setTimeout(() => {
                let serviceMessage = '';
                
                switch(service) {
                    case 'pvt-ltd':
                        serviceMessage = "I'm interested in registering a Private Limited Company. Can you tell me about the process and fees?";
                        break;
                    case 'llp':
                        serviceMessage = "I'd like to know more about Limited Liability Partnership registration. What are the requirements and costs?";
                        break;
                    case 'opc':
                        serviceMessage = "I'm a solo entrepreneur looking to register a One Person Company. What's the procedure?";
                        break;
                    default:
                        serviceMessage = "I'm interested in your company registration services. Can you provide more details?";
                }
                
                addMessage(serviceMessage, 'user');
                sendMessageToServer(serviceMessage);
            }, 1000);
            
            resetFollowUpCount();
            messageInput.focus();
        });
    });

    pricingChatButtons.forEach(button => {
        button.addEventListener('click', function() {
            const plan = this.getAttribute('data-plan');
            
            chatWidget.style.display = 'flex';
            chatBubble.style.display = 'none';
            
            if (!socket || socket.readyState !== WebSocket.OPEN) {
                connectWebSocket();
            }
            
            // Add a slight delay so the greeting appears first
            setTimeout(() => {
                let planMessage = '';
                
                switch(plan) {
                    case 'basic':
                        planMessage = "I'm interested in your Basic plan for company registration. Can you help me get started?";
                        break;
                    case 'standard':
                        planMessage = "I'd like to know more about your Standard incorporation package. What's included?";
                        break;
                    case 'premium':
                        planMessage = "I'm interested in the Premium incorporation package. Can you walk me through the benefits?";
                        break;
                    default:
                        planMessage = "I'd like to learn more about your pricing packages for company registration.";
                }
                
                addMessage(planMessage, 'user');
                sendMessageToServer(planMessage);
            }, 1000);
            
            resetFollowUpCount();
            messageInput.focus();
        });
    });

    sendMessage.addEventListener('click', function() {
        const text = messageInput.value.trim();
        
        if (text) {
            addMessage(text, 'user');
            sendMessageToServer(text);
            messageInput.value = '';
            resetFollowUpCount();
        }
    });

    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage.click();
        }
        
        // Reset inactivity timer when user is typing
        resetFollowUpCount();
    });

    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            const file = this.files[0];
            fileName.textContent = file.name;
            
            // Validate file type
            const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'];
            if (!validTypes.includes(file.type)) {
                addMessage("Please upload only images (JPEG, PNG, GIF, WEBP) or PDF files.", 'bot');
                fileInput.value = '';
                fileName.textContent = 'No file chosen';
            }
            
            // Validate file size (max 5MB)
            const maxSize = 5 * 1024 * 1024; // 5MB
            if (file.size > maxSize) {
                addMessage("The file is too large. Please upload a file smaller than 5MB.", 'bot');
                fileInput.value = '';
                fileName.textContent = 'No file chosen';
            }
        } else {
            fileName.textContent = 'No file chosen';
        }
    });

    documentUploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (fileInput.files.length === 0) {
            addMessage('Please select a file to upload', 'bot');
            return;
        }
        
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('document', file);
        
        // Use the server's session ID if available, otherwise fall back to client's ID
        const uploadSessionId = serverSessionId || sessionId;
        updateDebug(`Using session ID for document upload: ${uploadSessionId}`);
        formData.append('session_id', uploadSessionId);
        
        // Add cookie ID if available
        if (cookieId) {
            formData.append('cookie_id', cookieId);
            updateDebug(`Including cookie ID with document upload: ${cookieId}`);
        }
        
        try {
            // Disable the form during upload
            const submitButton = documentUploadForm.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
            
            // Show uploading status message
            addMessage(`Uploading ${file.name}... Please wait.`, 'bot');
            
            updateDebug(`Starting document upload: ${file.name}`);
            const response = await fetch('/upload-document', {
                method: 'POST',
                body: formData
            });
            
            // Re-enable the form
            submitButton.disabled = false;
            submitButton.innerHTML = 'Upload Document';
            
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            updateDebug(`Document upload result: ${JSON.stringify(result)}`);
            
            if (result.success) {
                addMessage("Document uploaded successfully! Our specialist will verify it shortly.", 'bot');
                documentUploadArea.style.display = 'none';
                adjustChatLayout();
                
                // Reset the form
                fileInput.value = '';
                fileName.textContent = 'No file chosen';
                
                // The verification result will come via WebSocket message
            } else {
                addMessage(`Error uploading document: ${result.error || 'Unknown error'}`, 'bot');
            }
        } catch (error) {
            updateDebug(`Error uploading document: ${error.message}`);
            console.error('Error uploading document:', error);
            addMessage(`Upload failed: ${error.message || 'Please check your connection and try again.'}`, 'bot');
            
            // Re-enable the form if it wasn't already
            const submitButton = documentUploadForm.querySelector('button[type="submit"]');
            submitButton.disabled = false;
            submitButton.innerHTML = 'Upload Document';
        }
    });

    paymentLink.addEventListener('click', function(e) {
        // Prevent the default link behavior (don't open in new tab)
        e.preventDefault();
        
        // Track that user clicked the payment link
        addMessage("I'm proceeding to make the payment now.", 'user');
        
        // Get the safe payment ID from the data attribute
        const paymentId = this.dataset.paymentId;
        
        // Log the payment ID we're using
        updateDebug(`Using payment ID for checkout: ${paymentId}`);
        
        // Open the Razorpay checkout modal
        openRazorpayCheckout(paymentId);
    });
    
    // Add a close button event for the payment area
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('payment-close')) {
            closePaymentArea();
        }
    });

    async function checkPaymentStatus(paymentId) {
        try {
            // If no payment ID is provided, try to extract it from the data attribute
            if (!paymentId && paymentLink.dataset.paymentId) {
                paymentId = paymentLink.dataset.paymentId;
            }
            
            if (!paymentId) {
                updateDebug('No payment ID available for status check');
                return;
            }
            
            // Use the server's session ID if available, otherwise fall back to client's ID
            const paymentSessionId = serverSessionId || sessionId;
            let url = `/check-payment/${paymentId}?session_id=${paymentSessionId}`;
            
            // Add cookie ID if available
            if (cookieId) {
                url += `&cookie_id=${cookieId}`;
                updateDebug(`Including cookie ID with payment check: ${cookieId}`);
            }
            
            updateDebug(`Checking payment status at: ${url}`);
            const response = await fetch(url);
            const result = await response.json();
            
            updateDebug(`Payment status check: ${JSON.stringify(result)}`);
            
            // Note: The server will send a WebSocket message if payment is complete
            // We don't need to do anything here since the server handles notifying the user
        } catch (error) {
            updateDebug(`Error checking payment status: ${error.message}`);
            console.error('Error checking payment status:', error);
        }
    }

    // Device fingerprinting and cookie management functions
    function generateDeviceId() {
        // Generate a device fingerprint based on browser information
        const components = [
            navigator.userAgent,
            navigator.language,
            screen.width + 'x' + screen.height,
            new Date().getTimezoneOffset(),
            navigator.platform,
            !!navigator.cookieEnabled,
            !!window.indexedDB,
            !!window.localStorage,
            !!window.sessionStorage
        ];
        
        // Simple hash function
        let hash = 0;
        const str = components.join('|');
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        
        // Convert to a string and make it positive
        return 'device_' + Math.abs(hash).toString(16);
    }
    
    function getDeviceInfo() {
        // Get device fingerprint info for tracking across sessions
        const deviceId = localStorage.getItem('deviceId') || generateDeviceId();
        localStorage.setItem('deviceId', deviceId); // Store for future use
        
        return {
            device_id: deviceId,
            platform: navigator.platform,
            screen_size: screen.width + 'x' + screen.height,
            user_agent: navigator.userAgent.substring(0, 100), // Truncate to avoid too much data
            language: navigator.language,
            last_visit: new Date().toISOString()
        };
    }
    
    // Cookie management functions with enhanced persistence
    function setCookie(name, value, days) {
        // Extended cookie lifetime for better persistence
        const expires = new Date();
        expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
        
        // Enhanced cookie settings for maximum compatibility and persistence
        // Using multiple storage mechanisms for redundancy
        try {
            // Primary: Standard cookie
            document.cookie = name + '=' + encodeURIComponent(value) +
                ';expires=' + expires.toUTCString() +
                ';path=/;SameSite=Lax';
                
            // Backup: localStorage (persistent)
            localStorage.setItem(name, value);
            
            // Session backup: sessionStorage (session only)
            sessionStorage.setItem(name, value);
            
            updateDebug(`Cookie set with redundant storage: ${name}=${value.substring(0, 10)}... (expires in ${days} days)`);
        } catch (e) {
            console.error('Error setting cookie:', e);
        }
    }

    function getCookie(name) {
        // Try to get from standard cookie first
        const nameEQ = name + '=';
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) {
                const value = decodeURIComponent(c.substring(nameEQ.length, c.length));
                updateDebug(`Cookie retrieved: ${name}=${value.substring(0, 10)}...`);
                return value;
            }
        }
        
        // Fallback to localStorage if cookie not found
        const localValue = localStorage.getItem(name);
        if (localValue) {
            updateDebug(`Cookie retrieved from localStorage: ${name}=${localValue.substring(0, 10)}...`);
            // Restore the cookie for future use
            setCookie(name, localValue, cookieLifetime);
            return localValue;
        }
        
        // Final fallback to sessionStorage
        const sessionValue = sessionStorage.getItem(name);
        if (sessionValue) {
            updateDebug(`Cookie retrieved from sessionStorage: ${name}=${sessionValue.substring(0, 10)}...`);
            return sessionValue;
        }
        
        updateDebug(`Cookie not found in any storage: ${name}`);
        return null;
    }

    // Minimize chat functionality with direct style manipulation for reliability
    minimizeChat.addEventListener('click', function() {
        if (minimized) {
            // Restore from minimized state
            chatWidget.classList.remove('minimized');
            
            // Restore previous height
            if (maximized) {
                // If it was maximized before minimizing, restore to full screen
                chatWidget.style.height = '100%';
            } else {
                // Otherwise restore to default height
                chatWidget.style.height = '96vh';
            }
            
            minimizeChat.innerHTML = '<i class="fas fa-minus"></i>';
            minimized = false;
            updateDebug('Chat restored from minimized state');
            
            // Focus the input field when restoring
            setTimeout(() => messageInput.focus(), 100);
        } else {
            // Apply minimized state
            chatWidget.classList.add('minimized');
            
            // Force height with inline styles
            const originalHeight = chatWidget.style.height; // Store original for later
            chatWidget.style.height = '70px';
            chatWidget.style.minHeight = '70px';
            chatWidget.style.maxHeight = '70px';
            
            minimizeChat.innerHTML = '<i class="fas fa-expand-alt"></i>';
            minimized = true;
            
            // Reset maximize state if it was maximized but keep track of it
            if (maximized) {
                chatWidget.classList.remove('maximized');
                maximizeChat.innerHTML = '<i class="fas fa-expand"></i>';
                // Don't set maximized to false, so we know to restore to maximized state
            }
            
            updateDebug('Chat minimized');
        }
    });
    
    // Maximize chat functionality with direct style manipulation for reliability
    if (maximizeChat) {
        maximizeChat.addEventListener('click', function() {
            if (maximized) {
                // Return to normal (non-maximized) state
                chatWidget.classList.remove('maximized');
                
                // Reset to default position and size
                chatWidget.style.top = '2vh';
                chatWidget.style.right = '2vw';
                chatWidget.style.bottom = '2vh';
                chatWidget.style.left = '2vw';
                chatWidget.style.width = '96vw';
                chatWidget.style.height = '96vh';
                chatWidget.style.borderRadius = '16px';
                
                maximizeChat.innerHTML = '<i class="fas fa-expand"></i>';
                maximized = false;
                updateDebug('Chat returned to normal size');
            } else {
                // Go to maximized (full-screen) state - direct style manipulation
                chatWidget.classList.add('maximized');
                
                // Force full screen with inline styles for maximum browser compatibility
                chatWidget.style.position = 'fixed';
                chatWidget.style.top = '0';
                chatWidget.style.right = '0';
                chatWidget.style.bottom = '0';
                chatWidget.style.left = '0';
                chatWidget.style.width = '100%';
                chatWidget.style.height = '100%';
                chatWidget.style.borderRadius = '0';
                chatWidget.style.margin = '0';
                
                maximizeChat.innerHTML = '<i class="fas fa-compress"></i>';
                maximized = true;
                
                // Ensure it's not minimized
                if (minimized) {
                    chatWidget.classList.remove('minimized');
                    chatWidget.style.height = '100%';
                    minimizeChat.innerHTML = '<i class="fas fa-minus"></i>';
                    minimized = false;
                }
                
                updateDebug('Chat maximized to full screen');
            }
            
            // Adjust layout after state change
            adjustChatLayout();
            
            // Focus the input field after maximizing
            setTimeout(() => messageInput.focus(), 100);
        });
    }

    // Initialize
    function initChat() {
        // Try to get cookie ID first (for user identification)
        cookieId = getCookie('registerKaroCookieId');
        updateDebug(`Initial cookie ID: ${cookieId || 'not found'}`);
        
        // Try to get session ID from cookie with enhanced persistence
        sessionId = getCookie('chatSessionId');
        
        // Get device fingerprint for session binding and tracking
        const deviceInfo = getDeviceInfo();
        
        // If no session ID found, generate a new one with device fingerprinting
        if (!sessionId) {
            // Create a session ID that includes device fingerprint for better tracking
            sessionId = 'session_' + deviceInfo.device_id.substring(0, 8) + '_' + Date.now();
            
            // Store in multiple places for redundancy with extended lifetime
            setCookie('chatSessionId', sessionId, cookieLifetime); // Set cookie to expire in 1 year
            
            updateDebug(`Generated new session ID using device fingerprinting: ${sessionId}`);
        } else {
            updateDebug(`Using existing session ID: ${sessionId}`);
        }
        
        // Enhanced user tracking - store detailed visit information in localStorage for persistence
        let userInfo;
        try {
            userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
            
            // Update or initialize user info
            if (!userInfo.firstVisit) {
                userInfo.firstVisit = new Date().toISOString();
                userInfo.visits = 1;
                userInfo.deviceId = deviceInfo.device_id;
            } else {
                userInfo.visits = (userInfo.visits || 0) + 1;
                
                // If device ID has changed but session is preserved, note this for tracking
                if (userInfo.deviceId && userInfo.deviceId !== deviceInfo.device_id) {
                    userInfo.previousDevices = userInfo.previousDevices || [];
                    if (!userInfo.previousDevices.includes(userInfo.deviceId)) {
                        userInfo.previousDevices.push(userInfo.deviceId);
                    }
                    userInfo.deviceId = deviceInfo.device_id;
                }
            }
            
            // Make sure the cookie ID is stored in user info if available
            if (cookieId && (!userInfo.cookieId || userInfo.cookieId !== cookieId)) {
                userInfo.cookieId = cookieId;
                updateDebug(`Updated user info with cookie ID: ${cookieId}`);
            }
            
            // Track detailed visit history
            if (!userInfo.visitHistory) {
                userInfo.visitHistory = [];
            }
            
            // Add current visit to history (limit to last 10 visits)
            userInfo.visitHistory.push({
                timestamp: new Date().toISOString(),
                screenSize: deviceInfo.screen_size,
                url: window.location.href
            });
            
            // Keep only the most recent 10 visits
            if (userInfo.visitHistory.length > 10) {
                userInfo.visitHistory = userInfo.visitHistory.slice(-10);
            }
            
            userInfo.lastActive = new Date().toISOString();
            
            // Store updated info in localStorage for persistence across browser sessions
            localStorage.setItem('userInfo', JSON.stringify(userInfo));
        } catch (e) {
            console.error('Error updating user info:', e);
        }
        
        // Connect to WebSocket
        connectWebSocket();
        
        // Auto-open chat for returning users or direct links
        if (window.location.hash === '#chat' || (userInfo && userInfo.visits > 1)) {
            setTimeout(() => {
                chatBubble.click();
            }, 1000);
        }
    }
    
    initChat();
});