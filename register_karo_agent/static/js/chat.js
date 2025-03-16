document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatWidget = document.getElementById('chat-widget');
    const chatBubble = document.getElementById('chat-bubble');
    const closeChat = document.getElementById('close-chat');
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

    // Variables
    let sessionId = null;
    let serverSessionId = null; // Store the server's assigned session ID
    let socket = null;
    let typingTimer = null;
    let inactivityTimer = null;
    let retryCount = 0;
    let followUpCount = 0;
    const maxRetries = 3;
    const maxFollowUps = 5; // Maximum number of follow-ups before backing off
    const baseInactivityTimeout = 120000; // 2 minutes initial timeout
    const reconnectInterval = 3000; // 3 seconds
    
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
            console.log('WebSocket already connected');
            return;
        }

        // Get the correct WebSocket URL based on the current location
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        socket = new WebSocket(wsUrl);
        
        socket.onopen = function() {
            console.log('WebSocket connected');
            retryCount = 0;
            
            // If we have a session ID from a previous connection, include it
            if (sessionId) {
                const reconnectMsg = {
                    type: 'message',
                    text: 'Reconnected to chat',
                    session_id: sessionId
                };
                socket.send(JSON.stringify(reconnectMsg));
            }
            
            // Send initial greeting on first connection
            if (!sessionId) {
                setTimeout(() => {
                    const botGreeting = "👋 Hello! I'm your RegisterKaro incorporation specialist. I can help you register your company quickly and efficiently. How can I assist you today?";
                    addMessage(botGreeting, 'bot');
                }, 500);
            }
        };
        
        socket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            
            if (data.type === 'session_info') {
                // Store the server's session ID
                serverSessionId = data.session_id;
                console.log('Received server session ID:', serverSessionId);
            } else if (data.type === 'message' || data.type === 'follow_up') {
                console.log('Adding message to chat:', data.text.substring(0, 50) + '...');
                addMessage(data.text, 'bot', data.type);
                resetFollowUpCount();
            } else if (data.type === 'show_document_upload') {
                showDocumentUploadForm();
            } else if (data.type === 'payment_link') {
                showPaymentLink(data.link);
            }
        };
        
        socket.onclose = function() {
            console.log('WebSocket connection closed');
            
            // Try to reconnect with exponential backoff
            if (retryCount < maxRetries) {
                const timeout = Math.min(30000, reconnectInterval * Math.pow(2, retryCount));
                console.log(`Attempting to reconnect in ${timeout/1000} seconds...`);
                
                setTimeout(() => {
                    retryCount++;
                    connectWebSocket();
                }, timeout);
            } else {
                console.error('Failed to reconnect after several attempts');
                addMessage('Connection lost. Please reload the page to continue chatting.', 'bot');
            }
        };
        
        socket.onerror = function(error) {
            console.error('WebSocket error:', error);
        };
    }

    function sendMessageToServer(text) {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected');
            addMessage('Connection lost. Trying to reconnect...', 'bot');
            connectWebSocket();
            return;
        }
        
        const message = {
            type: 'message',
            text: text
        };
        
        // Add session ID if we have one
        if (sessionId) {
            message.session_id = sessionId;
        }
        
        socket.send(JSON.stringify(message));
    }

    function resetInactivityTimer() {
        clearTimeout(inactivityTimer);
        
        // Only set a new timer if we haven't reached max follow-ups
        if (followUpCount < maxFollowUps) {
            // Get the appropriate timeout based on follow-up count
            const timeout = inactivityTimeouts[Math.min(followUpCount, inactivityTimeouts.length - 1)];
            
            console.log(`Setting inactivity timer: ${timeout/1000} seconds (follow-up #${followUpCount + 1})`);
            
            inactivityTimer = setTimeout(() => {
                if (socket && socket.readyState === WebSocket.OPEN && sessionId) {
                    console.log(`User inactive for ${timeout/1000} seconds, sending follow-up #${followUpCount + 1}`);
                    
                    // Check if payment area is visible to determine context
                    let context = null;
                    if (paymentArea.style.display === 'block') {
                        context = 'payment_pending';
                    }
                    
                    // Include follow-up count in the message to help server tailor response
                    const inactiveMsg = {
                        type: 'inactive',
                        session_id: sessionId,
                        context: context,
                        follow_up_count: followUpCount
                    };
                    
                    socket.send(JSON.stringify(inactiveMsg));
                    
                    // Increment follow-up count for next time
                    followUpCount++;
                }
            }, timeout);
        } else {
            console.log(`Maximum follow-ups (${maxFollowUps}) reached. No more follow-ups will be sent.`);
        }
    }
    
    // Reset follow-up count when user interacts
    function resetFollowUpCount() {
        if (followUpCount > 0) {
            console.log(`Resetting follow-up count from ${followUpCount} to 0 due to user activity`);
            followUpCount = 0;
        }
        resetInactivityTimer();
    }

    function showDocumentUploadForm() {
        documentUploadArea.style.display = 'block';
        paymentArea.style.display = 'none';
    }

    function showPaymentLink(link) {
        // Extract the payment ID from the link URL
        const paymentId = link.split('/').pop();
        
        // Store the payment ID and link for later use
        paymentLink.dataset.paymentId = paymentId;
        paymentLink.dataset.originalLink = link;
        
        // Display the payment area
        paymentArea.style.display = 'block';
    }

    // Initialize Razorpay checkout
    function openRazorpayCheckout(paymentId) {
        // Add a message showing that payment is being initialized
        addMessage("Opening secure payment gateway...", 'bot');
        
        // Use the Razorpay test key
        const razorpayKey = 'rzp_test_I98HfDwdi2qQ3T';
        
        // Get customer information if available (using defaults if not)
        const options = {
            key: razorpayKey,
            amount: 500, // Amount in paise (₹5)
            currency: 'INR',
            name: 'RegisterKaro',
            description: 'Private Limited Company Registration',
            image: 'https://ui-avatars.com/api/?name=RegisterKaro&background=0047ab&color=fff',
            order_id: '', // Leave blank for our simulated environment
            handler: function (response) {
                // Payment successful
                addMessage("Payment successful! Your transaction ID is: " + response.razorpay_payment_id, 'bot');
                
                // Check payment status on server
                checkPaymentStatus(paymentId);
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
                    addMessage("Payment process was cancelled. You can try again when you're ready.", 'bot');
                }
            },
            config: {
                display: {
                    blocks: {
                        utib: { // UPI payment block
                            name: "Pay using UPI",
                            instruments: [
                                {
                                    method: "upi"
                                }
                            ]
                        }
                    },
                    sequence: ["block.utib"],
                    preferences: {
                        show_default_blocks: false
                    }
                }
            }
        };
        
        // Create and open Razorpay checkout
        const razorpayCheckout = new Razorpay(options);
        razorpayCheckout.open();
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
        console.log('Using session ID for document upload:', uploadSessionId);
        
        formData.append('session_id', uploadSessionId);
        
        try {
            // Disable the form during upload
            const submitButton = documentUploadForm.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
            
            // Show uploading status message
            addMessage(`Uploading ${file.name}... Please wait.`, 'bot');
            
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
            console.log('Document upload result:', result);
            
            if (result.success) {
                addMessage("Document uploaded successfully! Our specialist will verify it shortly.", 'bot');
                documentUploadArea.style.display = 'none';
                
                // Reset the form
                fileInput.value = '';
                fileName.textContent = 'No file chosen';
                
                // The verification result will come via WebSocket message
            } else {
                addMessage(`Error uploading document: ${result.error || 'Unknown error'}`, 'bot');
            }
        } catch (error) {
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
        
        // Get the payment ID from the data attribute
        const paymentId = this.dataset.paymentId;
        
        // Open the Razorpay checkout modal
        openRazorpayCheckout(paymentId);
    });

    async function checkPaymentStatus(paymentId) {
        try {
            // If no payment ID is provided, try to extract it from the data attribute
            if (!paymentId && paymentLink.dataset.paymentId) {
                paymentId = paymentLink.dataset.paymentId;
            }
            
            if (!paymentId) {
                console.error('No payment ID available for status check');
                return;
            }
            
            // Use the server's session ID if available, otherwise fall back to client's ID
            const paymentSessionId = serverSessionId || sessionId;
            console.log('Using session ID for payment check:', paymentSessionId);
            
            const response = await fetch(`/check-payment/${paymentId}?session_id=${paymentSessionId}`);
            const result = await response.json();
            
            console.log('Payment status check:', result);
            
            // Note: The server will send a WebSocket message if payment is complete
            // We don't need to do anything here since the server handles notifying the user
        } catch (error) {
            console.error('Error checking payment status:', error);
        }
    }

    // Initialize
    function initChat() {
        // Generate a random session ID if we don't have one
        sessionId = localStorage.getItem('chatSessionId');
        if (!sessionId) {
            sessionId = 'session_' + Math.random().toString(36).substring(2, 15);
            localStorage.setItem('chatSessionId', sessionId);
        }
        
        // Connect to WebSocket
        connectWebSocket();
        
        // Auto-open chat if this is a direct chat link
        if (window.location.hash === '#chat') {
            setTimeout(() => {
                chatBubble.click();
            }, 1000);
        }
    }
    
    initChat();
});