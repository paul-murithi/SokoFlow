document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const messagesContainer = document.getElementById('messages-container');
    const chatViewport = document.getElementById('chat-viewport');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const btnSend = document.getElementById('btn-send');
    const phoneInput = document.getElementById('phone-input');
    const statusDot = document.getElementById('status-dot');
    const connectionStatus = document.getElementById('connection-status');
    const typingIndicator = document.getElementById('typing-indicator');

    // Debug Panel Elements
    const btnToggleDebug = document.getElementById('btn-toggle-debug');
    const debugPanel = document.getElementById('debug-panel');
    const debugClose = document.getElementById('debug-close');
    const debugWebhookUrl = document.getElementById('debug-webhook-url');
    const debugApiStatus = document.getElementById('debug-api-status');
    const debugPhoneDisplay = document.getElementById('debug-phone-display');
    const btnClearChat = document.getElementById('btn-clear-chat');
    const quickChips = document.querySelectorAll('.chip');

    // State
    let currentPhone = phoneInput.value.trim() || '254712345678';
    let knownMessageIds = new Set();
    let isWaitingForResponse = false;
    let pollTimer = null;
    let statusTimer = null;

    // Helper: format timestamp
    function formatTime(isoString) {
        if (!isoString) return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        try {
            const d = new Date(isoString);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    }

    // Scroll to bottom smoothly
    function scrollToBottom() {
        chatViewport.scrollTop = chatViewport.scrollHeight;
    }

    let responseTimeoutTimer = null;

    // Show / Hide Typing Indicator
    function setTyping(active) {
        isWaitingForResponse = active;
        if (responseTimeoutTimer) {
            clearTimeout(responseTimeoutTimer);
            responseTimeoutTimer = null;
        }

        if (active) {
            typingIndicator.classList.remove('hidden');
            btnSend.disabled = true;
            messageInput.disabled = true;

            // Timeout fallback if worker doesn't respond in 10s
            responseTimeoutTimer = setTimeout(() => {
                if (isWaitingForResponse) {
                    renderMessage({
                        id: 'timeout-' + Date.now(),
                        sender: 'bot',
                        type: 'text',
                        text: '⚠️ Still waiting for response. Check if Celery worker is running:\n`uv run celery -A app.tasks worker -Q conversation_tasks`',
                        timestamp: new Date().toISOString()
                    });
                    setTyping(false);
                }
            }, 10000);
        } else {
            typingIndicator.classList.add('hidden');
            btnSend.disabled = false;
            messageInput.disabled = false;
            messageInput.focus();
        }
        scrollToBottom();
    }

    // Render a single message
    function renderMessage(msg) {
        if (knownMessageIds.has(msg.id)) {
            return; // Avoid duplicate rendering
        }
        knownMessageIds.add(msg.id);

        const isUser = msg.sender === 'user';
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${isUser ? 'user' : 'bot'}`;

        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${isUser ? 'user-bubble' : 'bot-bubble'}`;

        if (msg.type === 'document') {
            const card = document.createElement('div');
            card.className = 'document-card';

            const lenKb = msg.document_length ? ` • ${(msg.document_length / 1024).toFixed(1)} KB` : '';
            card.innerHTML = `
                <div class="document-header">
                    <span class="document-icon">📄</span>
                    <div class="document-info">
                        <span class="document-filename">${escapeHtml(msg.filename || 'Document.pdf')}</span>
                        <span class="document-meta">PDF Document${lenKb}</span>
                    </div>
                </div>
                ${msg.caption ? `<div class="document-caption">${escapeHtml(msg.caption)}</div>` : ''}
            `;
            bubble.appendChild(card);
        } else {
            bubble.textContent = msg.text || '';
        }

        const footer = document.createElement('div');
        footer.className = 'message-footer';
        footer.innerHTML = `<span>${formatTime(msg.timestamp)}</span>${isUser ? '<span>✓✓</span>' : ''}`;
        bubble.appendChild(footer);

        wrapper.appendChild(bubble);
        messagesContainer.appendChild(wrapper);

        // If a bot reply arrived, stop typing indicator
        if (!isUser && isWaitingForResponse) {
            setTyping(false);
        }

        scrollToBottom();
    }

    // Escape HTML strings for security
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Fetch messages from simulator API
    async function fetchMessages() {
        try {
            const response = await fetch(`/api/messages?phone=${encodeURIComponent(currentPhone)}`);
            if (!response.ok) return;
            const data = await response.json();

            if (data.messages && Array.isArray(data.messages)) {
                data.messages.forEach(msg => renderMessage(msg));
            }
        } catch (err) {
            console.error('Error fetching messages:', err);
        }
    }

    // Fetch system status
    async function fetchStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error('Status check failed');
            const data = await response.json();

            if (data.api_connected) {
                statusDot.className = 'status-dot online';
                connectionStatus.textContent = 'Connected to backend';
                debugApiStatus.textContent = '● Connected';
                debugApiStatus.className = 'value status-ok';
            } else {
                statusDot.className = 'status-dot offline';
                connectionStatus.textContent = 'Backend unreachable';
                debugApiStatus.textContent = '● Disconnected';
                debugApiStatus.className = 'value danger';
            }
            if (data.webhook_url) {
                debugWebhookUrl.textContent = data.webhook_url;
            }
        } catch (err) {
            statusDot.className = 'status-dot offline';
            connectionStatus.textContent = 'Simulator offline';
            debugApiStatus.textContent = '● Offline';
            debugApiStatus.className = 'value danger';
        }
    }

    // Send a message
    async function sendMessage(text) {
        if (!text || isWaitingForResponse) return;

        setTyping(true);
        messageInput.value = '';

        try {
            const response = await fetch('/api/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    phone: currentPhone,
                    message: text
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to send (HTTP ${response.status})`);
            }

            // Immediately poll for new messages
            await fetchMessages();
        } catch (err) {
            console.error('Error sending message:', err);
            // Render local error bubble if webhook unreachable
            renderMessage({
                id: 'err-' + Date.now(),
                sender: 'bot',
                type: 'text',
                text: '⚠️ Could not send message to SokoFlow backend. Please ensure backend services are running.',
                timestamp: new Date().toISOString()
            });
            setTyping(false);
        }
    }

    // Clear chat
    async function clearChat() {
        try {
            await fetch('/api/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone: currentPhone })
            });
        } catch (e) {
            console.error('Failed to clear chat on server:', e);
        }
        messagesContainer.innerHTML = '';
        knownMessageIds.clear();
        setTyping(false);
    }

    // Event Handlers
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = messageInput.value.trim();
        if (text) {
            sendMessage(text);
        }
    });

    phoneInput.addEventListener('change', () => {
        const val = phoneInput.value.trim();
        if (val && val !== currentPhone) {
            currentPhone = val;
            debugPhoneDisplay.textContent = currentPhone;
            messagesContainer.innerHTML = '';
            knownMessageIds.clear();
            fetchMessages();
        }
    });

    btnToggleDebug.addEventListener('click', () => {
        debugPanel.classList.toggle('hidden');
    });

    debugClose.addEventListener('click', () => {
        debugPanel.classList.add('hidden');
    });

    btnClearChat.addEventListener('click', () => {
        if (confirm('Clear chat history for this phone number?')) {
            clearChat();
        }
    });

    quickChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const cmd = chip.getAttribute('data-cmd');
            if (cmd) {
                sendMessage(cmd);
            }
        });
    });

    // Initialize & Poll
    debugPhoneDisplay.textContent = currentPhone;
    fetchStatus();
    fetchMessages();

    pollTimer = setInterval(fetchMessages, 1000);
    statusTimer = setInterval(fetchStatus, 5000);
});
