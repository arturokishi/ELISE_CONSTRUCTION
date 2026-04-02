console.log("chat.js loaded");

/* ===============================
   GLOBAL STATE
================================ */
let currentChatUser = null;
let currentConversationId = null;
let csrftoken = null;
let messageRefreshInterval = null;
let conversationBlocked = false;
let currentPanelProducts = [];

let usersList,
    messagesContainer,
    messageInput,
    sendBtn,
    fileBtn,
    fileInput,
    messageInputContainer,
    currentUserName,
    currentUserInfo,
    currentUserAvatar;

/* ===============================
   INIT
================================ */
document.addEventListener('DOMContentLoaded', () => {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) csrftoken = metaTag.getAttribute('content');

    usersList           = document.getElementById('usersList');
    messagesContainer   = document.getElementById('messagesContainer');
    messageInput        = document.getElementById('messageInput');
    sendBtn             = document.getElementById('sendBtn');
    fileBtn             = document.getElementById('fileBtn');
    fileInput           = document.getElementById('fileInput');
    messageInputContainer = document.getElementById('messageInputContainer');
    currentUserName     = document.getElementById('currentUserName');
    currentUserInfo     = document.getElementById('currentUserInfo');
    currentUserAvatar   = document.getElementById('currentUserAvatar');

    if (!usersList || !messagesContainer || !messageInput || !sendBtn) {
        console.error("Critical DOM elements missing!");
        return;
    }

    wireEvents();
    loadUsers();

    // Mostrar input desde la pantalla de bienvenida para que el usuario pueda escribir directamente
    // El primer mensaje abrirá automáticamente la conversación con EliceBot
    const conversationId = getQueryParam('conversation');
    if (conversationId) {
        selectConversationById(conversationId);
    } else {
        // Pre-mostrar el input en modo "bienvenida": al escribir se abre el bot
        if (messageInputContainer) messageInputContainer.style.display = 'flex';
        if (messageInput) {
            messageInput.placeholder = 'Escríbeme un material o haz una pregunta…';
            // Interceptar primer mensaje para abrir bot automáticamente
            messageInput._welcomeMode = true;
        }
    }
});

/* ===============================
   HELPERS
================================ */
function getQueryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(date = new Date()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/* ===============================
   LOAD USERS
================================ */
async function loadUsers() {
    try {
        const res = await fetch('/chat/users/');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!data.users || !data.users.length) {
            usersList.innerHTML = `<div style="padding:20px;color:#475569;text-align:center;font-size:0.82rem;">
                Aún no tienes proveedores conectados.<br>Habla con EliceBot para comenzar.
            </div>`;
            return;
        }
        displayUsers(data.users);
    } catch (error) {
        console.error("Error loading users:", error);
        usersList.innerHTML = `<div style="padding:16px;color:#ef4444;font-size:0.8rem;text-align:center;">
            Error cargando contactos
        </div>`;
    }
}

/* ===============================
   DISPLAY USERS
================================ */
function displayUsers(users) {
    if (!usersList) return;
    usersList.innerHTML = '';

    const isClient = document.body.dataset.userRole === 'client';

    if (isClient) {
        // Filter out bot — it's shown separately in the pinned card
        const suppliers = users.filter(u => !u.is_bot);
        const uniqueSuppliers = [...new Map(suppliers.map(u => [u.id, u])).values()];

        if (uniqueSuppliers.length === 0) {
            usersList.innerHTML = `<div style="padding:16px;color:#334155;font-size:0.78rem;text-align:center;line-height:1.6;">
                Habla con EliceBot para conectarte con proveedores de materiales.
            </div>`;
        } else {
            // Group by category
            const byCategory = {};
            const seenInCat = {};

            uniqueSuppliers.forEach(user => {
                const cats = (user.categories && user.categories.length > 0)
                    ? [...new Set(user.categories)]
                    : ['Otros'];

                cats.forEach(cat => {
                    if (!byCategory[cat]) { byCategory[cat] = []; seenInCat[cat] = new Set(); }
                    if (!seenInCat[cat].has(user.id)) {
                        seenInCat[cat].add(user.id);
                        byCategory[cat].push(user);
                    }
                });
            });

            Object.keys(byCategory).sort().forEach(cat => {
                if (!byCategory[cat].length) return;
                const label = document.createElement('div');
                label.className = 'cat-label';
                label.textContent = cat;
                usersList.appendChild(label);
                byCategory[cat].forEach(u => usersList.appendChild(createUserItem(u)));
            });
        }
    } else {
        // Supplier/admin view — show all clients grouped by role
        const groups = { client: 'Clientes', supplier: 'Proveedores', admin: 'Administradores' };
        const grouped = {};
        const seen = new Set();

        users.forEach(u => {
            if (seen.has(u.id)) return;
            seen.add(u.id);
            const r = u.role || 'client';
            if (!grouped[r]) grouped[r] = [];
            grouped[r].push(u);
        });

        Object.keys(groups).forEach(role => {
            if (!grouped[role] || !grouped[role].length) return;
            const label = document.createElement('div');
            label.className = 'cat-label';
            label.textContent = groups[role];
            usersList.appendChild(label);
            grouped[role].forEach(u => usersList.appendChild(createUserItem(u)));
        });
    }

    // Wire click events
    usersList.querySelectorAll('.user-item').forEach(item => {
        item.addEventListener('click', function() {
            usersList.querySelectorAll('.user-item').forEach(i => i.classList.remove('active'));
            document.getElementById('botCard')?.classList.remove('active');
            this.classList.add('active');
            selectUser(this.dataset.userId);
        });
    });
}

/* ===============================
   CREATE USER ITEM
================================ */
function createUserItem(user) {
    const name = (user.first_name && user.last_name)
        ? `${user.first_name} ${user.last_name}`
        : user.username;
    const avatarColor = user.avatar_color || '#f59e0b';
    const initial = name.charAt(0).toUpperCase();

    const item = document.createElement('div');
    item.className = 'user-item';
    item.dataset.userId = user.id;

    const lastMsg = user.last_message
        ? `<div class="last-msg">${escapeHtml(user.last_message)}</div>`
        : '';

    const company = user.company
        ? `<div class="user-role">${escapeHtml(user.company)}</div>`
        : `<div class="user-role">${escapeHtml(user.role || '')}</div>`;

    const unreadBadge = user.unread_count
        ? `<div class="unread-badge">${user.unread_count}</div>`
        : '';

    item.innerHTML = `
        <div class="user-avatar" style="background:${avatarColor}; color:#0f172a;">${initial}</div>
        <div class="user-info">
            <div class="user-name">${escapeHtml(name)}<span class="status-dot status-online"></span></div>
            ${company}
            ${lastMsg}
        </div>
        ${unreadBadge}
    `;
    return item;
}

/* ===============================
   BOT CARD CLICK
================================ */
function selectBotFromCard() {
    document.getElementById('botCard')?.classList.add('active');
    usersList.querySelectorAll('.user-item').forEach(i => i.classList.remove('active'));

    // Find bot user id from users list data
    fetch('/chat/users/')
        .then(r => r.json())
        .then(data => {
            const bot = data.users.find(u => u.is_bot);
            if (bot) selectUser(bot.id);
        });
}

/* ===============================
   SELECT USER
================================ */
async function selectUser(userId) {
    if (!userId) return;

    currentChatUser = null;
    currentConversationId = null;

    // Hide bot welcome
    const welcome = document.getElementById('botWelcome');
    if (welcome) welcome.style.display = 'none';

    // Clear messages (keep welcome hidden)
    messagesContainer.innerHTML = '';
    setConversationState(true);

    if (messageRefreshInterval) {
        clearInterval(messageRefreshInterval);
        messageRefreshInterval = null;
    }

    try {
        const res = await fetch(`/chat/conversation/${userId}/`);

        if (!res.ok) {
            if (res.status === 403) {
                const err = await res.json();
                showChatPlaceholder('🚫', 'Sin acceso', err.error || 'Habla con EliceBot para conectarte con este proveedor.');
                setConversationState(true);
                return;
            }
            throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();
        if (!data.other_user) return;

        currentChatUser = data.other_user;
        currentConversationId = data.conversation_id;

        updateChatHeader(data.other_user);
        displayMessages(data.messages || []);

        // Bot welcome message if no history
        const isBot = data.other_user.username === 'elicebot';
        if (isBot && (!data.messages || !data.messages.length)) {
            setTimeout(() => {
                appendMessage({
                    content: "Hola 👋 soy EliceBot.\n\nPuedo conectarte con proveedores de materiales de construcción. Solo escríbeme el material que necesitas:\n\n• 🔩 Acero\n• 🎨 Pintura\n• 🏗️ Cemento\n• 🪟 Aluminio\n• 🪞 Vidrio",
                    is_sent: false,
                    is_bot: true,
                    timestamp: formatTime()
                });
            }, 400);
        }

        if (messageInputContainer) messageInputContainer.style.display = 'flex';
        setConversationState(false);

        // Quote pill & header button visibility
        const isSupplier = data.other_user.role === 'supplier';
        const quotePill = document.getElementById('quotePillBtn');
        if (quotePill) quotePill.classList.toggle('visible', isSupplier);

        const quoteBtn = document.getElementById('quoteBtn');
        if (quoteBtn) quoteBtn.disabled = !isSupplier;

        const whatsappBtn = document.getElementById('whatsappBtn');
        if (whatsappBtn) {
            whatsappBtn.disabled = !(isSupplier && data.other_user.whatsapp);
            whatsappBtn.dataset.whatsapp = data.other_user.whatsapp || '';
        }

        const catalogBtn = document.getElementById('catalogBtn');
        if (catalogBtn) {
            const hasCatalog = isSupplier && data.other_user.has_catalog;
            catalogBtn.style.display = hasCatalog ? 'inline-flex' : 'none';
            catalogBtn.disabled = !hasCatalog;
        }

        // Load product panel if supplier
        if (isSupplier) {
            loadProductPanel(data.other_user.id);
        } else {
            closeProductPanel();
        }

        // Update bot card style
        if (isBot) {
            document.getElementById('botCard')?.classList.add('active');
            document.getElementById('currentUserAvatar')?.classList.add('bot-style');
        } else {
            document.getElementById('botCard')?.classList.remove('active');
            document.getElementById('currentUserAvatar')?.classList.remove('bot-style');
        }

        startMessageRefresh();

    } catch (error) {
        console.error("Select user error:", error);
        showChatPlaceholder('❌', 'Error', error.message);
    }
}

function showChatPlaceholder(icon, title, text) {
    messagesContainer.innerHTML = `
        <div class="no-chat-selected">
            <div class="no-chat-selected-icon">${icon}</div>
            <strong style="color:var(--text)">${title}</strong>
            <span style="font-size:0.85rem;text-align:center;max-width:300px;">${escapeHtml(text)}</span>
        </div>`;
}

/* ===============================
   SELECT BY CONVERSATION ID
================================ */
async function selectConversationById(conversationId) {
    if (!conversationId) return;

    if (messageRefreshInterval) { clearInterval(messageRefreshInterval); messageRefreshInterval = null; }

    try {
        const res = await fetch(`/chat/conversation/by-id/${conversationId}/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        currentChatUser = data.other_user;
        currentConversationId = conversationId;

        updateChatHeader(data.other_user);
        displayMessages(data.messages || []);

        if (messageInputContainer) messageInputContainer.style.display = 'flex';

        const welcome = document.getElementById('botWelcome');
        if (welcome) welcome.style.display = 'none';

        startMessageRefresh();
    } catch (error) {
        console.error("Conversation load error:", error);
    }
}

/* ===============================
   HEADER UPDATE
================================ */
function updateChatHeader(user) {
    if (!user) return;

    const name = (user.first_name && user.last_name)
        ? `${user.first_name} ${user.last_name}`
        : user.username;

    const isBot = user.username === 'elicebot';

    if (currentUserName) currentUserName.textContent = isBot ? 'EliceBot' : name;

    if (currentUserAvatar) {
        currentUserAvatar.textContent = isBot ? '🤖' : name.charAt(0).toUpperCase();
        currentUserAvatar.style.background = isBot ? '#6366f1' : (user.avatar_color || '#f59e0b');
        currentUserAvatar.style.color = isBot ? '#fff' : '#0f172a';
    }

    let sub = '';
    if (isBot) sub = 'Asistente de materiales • IA';
    else {
        sub = user.role || '';
        if (user.company) sub += ` • ${user.company}`;
    }

    const infoText = document.getElementById('currentUserInfoText');
    if (infoText) infoText.textContent = sub;
    else if (currentUserInfo) currentUserInfo.textContent = sub;

    const onlineDot = document.getElementById('headerOnlineDot');
    if (onlineDot) onlineDot.style.display = 'inline-block';
}

/* ===============================
   DISPLAY MESSAGES
================================ */
function displayMessages(messages) {
    if (!messagesContainer) return;
    messagesContainer.innerHTML = '';

    if (!messages || messages.length === 0) return;

    messages.forEach(msg => appendMessage(msg, false));
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function appendMessage(message, shouldScroll = true) {
    if (!messagesContainer) return;

    // Dedup by ID
    if (message.id) {
        const existing = messagesContainer.querySelector(`[data-message-id="${message.id}"]`);
        if (existing) return;
    }

    const isBot = currentChatUser && currentChatUser.username === 'elicebot' && !message.is_sent;
    const isQuote = message.content && message.content.includes('SOLICITUD DE COTIZACIÓN');

    const div = document.createElement('div');
    div.className = `message ${message.is_sent ? 'sent' : 'received'}${isBot ? ' bot-msg' : ''}`;
    if (message.id) div.dataset.messageId = String(message.id);

    let contentHtml;
    if (isQuote && !message.is_sent) {
        contentHtml = renderQuoteCard(message.content);
    } else {
        contentHtml = `<div class="message-content">${escapeHtml(message.content)}</div>`;
    }

    div.innerHTML = `
        ${contentHtml}
        <div class="message-time">${message.timestamp || formatTime()}</div>
    `;

    messagesContainer.appendChild(div);
    if (shouldScroll) messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function renderQuoteCard(content) {
    // Parse the formatted quote message into a visual card
    const lines = content.split('\n').filter(l => l.trim() && !l.includes('━'));
    const rows = lines.slice(1).filter(l => l.includes(':'));

    let rowsHtml = rows.map(line => {
        const [label, ...rest] = line.replace(/\*\*/g, '').split(':');
        return `<div class="quote-card-msg-row">
            <span class="quote-card-msg-label">${escapeHtml(label.trim())}</span>
            <span class="quote-card-msg-value">${escapeHtml(rest.join(':').trim())}</span>
        </div>`;
    }).join('');

    return `<div class="quote-card-msg">
        <div class="quote-card-msg-title">📋 Solicitud de Cotización</div>
        ${rowsHtml}
    </div>`;
}

/* ===============================
   MATERIAL CHIPS (bot welcome)
================================ */
function sendMaterialChip(material) {
    // Find bot and open conversation, then send the message
    fetch('/chat/users/')
        .then(r => r.json())
        .then(data => {
            const bot = data.users.find(u => u.is_bot);
            if (!bot) return;

            // Select bot conversation first
            document.getElementById('botCard')?.classList.add('active');

            fetch(`/chat/conversation/${bot.id}/`)
                .then(r => r.json())
                .then(convData => {
                    currentChatUser = convData.other_user;
                    currentConversationId = convData.conversation_id;

                    const welcome = document.getElementById('botWelcome');
                    if (welcome) welcome.style.display = 'none';

                    updateChatHeader(convData.other_user);
                    displayMessages(convData.messages || []);
                    if (messageInputContainer) messageInputContainer.style.display = 'flex';
                    setConversationState(false);
                    startMessageRefresh();

                    // Send the chip message
                    if (messageInput) {
                        messageInput.value = material;
                        sendMessage();
                    }
                });
        });
}

/* ===============================
   PRODUCT PANEL
================================ */
async function loadProductPanel(supplierId) {
    const layout = document.getElementById('chatLayout');
    const content = document.getElementById('productPanelContent');

    if (!layout || !content) return;

    content.innerHTML = '<div class="loader" style="margin:30px auto;"></div>';
    layout.classList.add('panel-open');

    try {
        const res = await fetch(`/chat/quote-form/${supplierId}/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        content.innerHTML = '';

        if (!data.categories || !data.categories.length) {
            content.innerHTML = `<div class="panel-empty">Este proveedor no tiene productos configurados aún.</div>`;
            return;
        }

        let productCount = 0;
        data.categories.forEach(cat => {
            if (!cat.products || !cat.products.length) return;

            const catLabel = document.createElement('div');
            catLabel.style.cssText = 'font-size:0.7rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;padding:8px 4px 4px;';
            catLabel.textContent = cat.name;
            content.appendChild(catLabel);

            cat.products.forEach(product => {
                productCount++;
                const card = document.createElement('div');
                card.className = 'panel-product-card';
                card.innerHTML = `
                    ${product.image_url
                        ? `<img class="panel-product-img" src="${product.image_url}" alt="${escapeHtml(product.name)}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'panel-product-placeholder\\'>📦</div>'">`
                        : `<div class="panel-product-placeholder">📦</div>`
                    }
                    <div class="panel-product-body">
                        <div class="panel-product-name">${escapeHtml(product.name)}</div>
                        <div>
                            ${product.base_price
                                ? `<span class="panel-product-price">$${product.base_price}</span>
                                   <span class="panel-product-unit"> / ${escapeHtml(product.unit)}</span>`
                                : `<span class="panel-product-unit">Precio a consultar</span>`
                            }
                        </div>
                        <button class="panel-quote-btn" onclick='prefillQuote(${JSON.stringify({id:product.id, name:product.name, price:product.base_price, unit:product.unit})})'>
                            📋 Cotizar este producto
                        </button>
                    </div>
                `;
                content.appendChild(card);
            });
        });

        if (productCount === 0) {
            content.innerHTML = `<div class="panel-empty">Sin productos activos.</div>`;
        }

    } catch (err) {
        console.error('Panel load error:', err);
        content.innerHTML = `<div class="panel-empty">Error cargando productos.</div>`;
    }
}

function closeProductPanel() {
    const layout = document.getElementById('chatLayout');
    if (layout) layout.classList.remove('panel-open');
}

function prefillQuote(product) {
    // Open quote modal pre-filled with this product
    openQuoteModal();
    setTimeout(() => {
        const select = document.getElementById('quote-product');
        if (!select) return;
        for (let opt of select.options) {
            try {
                const val = JSON.parse(opt.value);
                if (val.id === product.id) { select.value = opt.value; break; }
            } catch(e) {}
        }
    }, 600);
}

/* ===============================
   REFRESH MESSAGES
================================ */
function startMessageRefresh() {
    if (messageRefreshInterval) clearInterval(messageRefreshInterval);
    messageRefreshInterval = setInterval(refreshMessages, 5000);
}

async function refreshMessages() {
    if (!currentConversationId) return;
    try {
        const res = await fetch(`/chat/conversation/by-id/${currentConversationId}/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.messages && messagesContainer) {
            const wasAtBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop <= messagesContainer.clientHeight + 100;
            data.messages.forEach(msg => appendMessage(msg, false));
            if (wasAtBottom) messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    } catch (error) {
        console.error("Refresh error:", error);
    }
}

/* ===============================
   SEND MESSAGE
================================ */
async function sendMessage() {
    if (!messageInput) return;
    const content = messageInput.value.trim();
    if (!content) return;

    // Si no hay conversación activa (welcome mode), abrir bot primero
    if (!currentChatUser) {
        if (messageInput._welcomeMode) {
            messageInput._welcomeMode = false;
            messageInput.placeholder = 'Escribe tu mensaje…';
            // Abrir bot y luego enviar el mensaje
            fetch('/chat/users/')
                .then(r => r.json())
                .then(data => {
                    const bot = data.users?.find(u => u.is_bot);
                    if (!bot) return;
                    document.getElementById('botCard')?.classList.add('active');
                    fetch(`/chat/conversation/${bot.id}/`)
                        .then(r => r.json())
                        .then(convData => {
                            currentChatUser = convData.other_user;
                            currentConversationId = convData.conversation_id;
                            const welcome = document.getElementById('botWelcome');
                            if (welcome) welcome.style.display = 'none';
                            updateChatHeader(convData.other_user);
                            displayMessages(convData.messages || []);
                            setConversationState(false);
                            startMessageRefresh();
                            // Ahora sí enviamos
                            messageInput.value = content;
                            sendBtn?.classList.add('active');
                            sendMessage();
                        });
                });
        }
        return;
    }

    const tempId = 'temp-' + Date.now();
    appendMessage({ id: tempId, content, is_sent: true, timestamp: formatTime() });
    const tempEl = messagesContainer.querySelector(`[data-message-id="${tempId}"]`);

    // Reset textarea
    messageInput.value = '';
    messageInput.style.height = 'auto';
    sendBtn?.classList.remove('active');

    // Show typing indicator if bot
    const isBot = currentChatUser?.username === 'elicebot';
    if (isBot) showTypingIndicator();

    try {
        const res = await fetch('/chat/send/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ user_id: currentChatUser.id, content, conversation_id: currentConversationId })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${res.status}`);
        }

        const data = await res.json();
        if (data.message_id && tempEl) tempEl.dataset.messageId = String(data.message_id);

        if (data.bot_reply) {
            setTimeout(() => {
                hideTypingIndicator();
                appendMessage({
                    id: data.bot_reply_id,
                    content: data.bot_reply,
                    is_sent: false,
                    is_bot: true,
                    timestamp: formatTime()
                });
                // Reload users after bot connects to new suppliers
                setTimeout(loadUsers, 1000);
            }, 600);
        } else {
            hideTypingIndicator();
        }
    } catch (error) {
        console.error("Send error:", error);
        hideTypingIndicator();
        if (tempEl) tempEl.querySelector('.message-content').style.opacity = '0.5';
    }
}

/* ===============================
   CONVERSATION STATE
================================ */
function setConversationState(blocked) {
    conversationBlocked = blocked;
    const ids = ['quoteBtn', 'whatsappBtn', 'catalogBtn', 'sendBtn'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = blocked;
    });
    if (messageInput) messageInput.disabled = blocked;
    if (messageInputContainer) messageInputContainer.style.display = blocked ? 'none' : 'flex';
}

/* ===============================
   QUOTE MODAL
================================ */
function openQuoteModal() {
    if (conversationBlocked || !currentChatUser || !currentConversationId) {
        alert('Habla con EliceBot para conectarte con este proveedor primero.');
        return;
    }
    loadQuoteForm();
}

function closeQuoteModal() {
    const modal = document.getElementById('quoteModal');
    if (modal) modal.style.display = 'none';
    document.getElementById('dynamicQuoteForm')?.reset();
    const opts = document.getElementById('product-options-container');
    if (opts) opts.innerHTML = '';
}

async function loadQuoteForm() {
    const modal = document.getElementById('quoteModal');
    const loading = document.getElementById('quote-form-loading');
    const container = document.getElementById('quote-form-container');
    const supplierName = document.getElementById('quote-supplier-name');

    if (!modal) return;
    modal.style.display = 'flex';
    loading.style.display = 'block';
    container.style.display = 'none';

    if (supplierName) {
        const name = (currentChatUser.first_name && currentChatUser.last_name)
            ? `${currentChatUser.first_name} ${currentChatUser.last_name}`
            : currentChatUser.username;
        supplierName.textContent = `Proveedor: ${name}${currentChatUser.company ? ' · ' + currentChatUser.company : ''}`;
    }

    try {
        const res = await fetch(`/chat/quote-form/${currentChatUser.id}/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!data.categories || !data.categories.length) {
            loading.innerHTML = `
                <div style="text-align:center;padding:20px;">
                    <div style="font-size:2.5rem;margin-bottom:12px;">💬</div>
                    <p style="font-weight:600;margin-bottom:8px;">Este proveedor cotiza por chat directo.</p>
                    <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:16px;">Escríbele en el chat o contáctalo por WhatsApp.</p>
                    <button onclick="closeQuoteModal()" style="padding:8px 20px;background:var(--primary);color:white;border:none;border-radius:8px;cursor:pointer;font-family:'DM Sans',sans-serif;">
                        ← Volver al chat
                    </button>
                </div>`;
            return;
        }

        const select = document.getElementById('quote-product');
        select.innerHTML = '<option value="">Selecciona un producto</option>';

        let count = 0;
        data.categories.forEach(cat => {
            if (!cat.products || !cat.products.length) return;
            const group = document.createElement('optgroup');
            group.label = cat.name;
            cat.products.forEach(p => {
                count++;
                const opt = document.createElement('option');
                opt.value = JSON.stringify({ id: p.id, name: p.name, price: p.base_price, unit: p.unit, options: p.options || [] });
                opt.textContent = `${p.name}${p.base_price ? ` — $${p.base_price}/${p.unit}` : ''}`;
                group.appendChild(opt);
            });
            select.appendChild(group);
        });

        if (!count) {
            loading.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:20px;">Sin productos activos para cotizar.</p>`;
            return;
        }

        loading.style.display = 'none';
        container.style.display = 'block';

    } catch (err) {
        loading.innerHTML = `<p style="color:#ef4444;text-align:center;">Error: ${err.message}</p>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('quote-product')?.addEventListener('change', function() {
        const container = document.getElementById('product-options-container');
        if (!container) return;
        container.innerHTML = '';
        if (!this.value) return;
        const product = JSON.parse(this.value);
        (product.options || []).forEach(opt => {
            const div = document.createElement('div');
            div.className = 'form-group';
            div.innerHTML = `
                <label class="form-label">${opt.name}${opt.required ? ' *' : ''}</label>
                <select id="opt-${opt.name}" class="form-control" ${opt.required ? 'required' : ''}>
                    <option value="">Selecciona...</option>
                    ${(opt.options || []).map(o => `<option value="${o}">${o}</option>`).join('')}
                </select>`;
            container.appendChild(div);
        });
    });
});

async function submitDynamicQuote() {
    const productSelect = document.getElementById('quote-product');
    if (!productSelect.value) { alert('Selecciona un producto'); return; }

    const product = JSON.parse(productSelect.value);
    const quantity = document.getElementById('quote-quantity').value;
    const notes = document.getElementById('quote-notes').value;

    const options = {};
    (product.options || []).forEach(opt => {
        const el = document.getElementById(`opt-${opt.name}`);
        if (el && el.value) options[opt.name] = el.value;
    });

    const quoteData = { product_id: product.id, product_name: product.name, quantity: parseInt(quantity), options, notes, estimated_total: (product.price || 0) * quantity };
    const message = formatQuoteMessage(quoteData, currentChatUser);

    try {
        const res = await fetch('/chat/send/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ user_id: currentChatUser.id, content: message, conversation_id: currentConversationId })
        });
        if (res.ok) {
            closeQuoteModal();
            refreshMessages();
        } else throw new Error('Error al enviar');
    } catch (err) {
        alert('❌ Error al enviar la cotización');
    }
}

function formatQuoteMessage(data, supplier) {
    const opts = Object.entries(data.options).map(([k, v]) => `  • ${k}: ${v}`).join('\n');
    return `📋 SOLICITUD DE COTIZACIÓN\n` +
        `━━━━━━━━━━━━━━━━━━━\n` +
        `Producto: ${data.product_name}\n` +
        `Cantidad: ${data.quantity}\n` +
        `${opts ? `Especificaciones:\n${opts}\n` : ''}` +
        `Total estimado: $${data.estimated_total}\n` +
        `Notas: ${data.notes || 'Ninguna'}\n` +
        `━━━━━━━━━━━━━━━━━━━`;
}

/* ===============================
   CATALOG
================================ */
async function openCatalogModal() {
    if (!currentChatUser || conversationBlocked) return;
    const modal = document.getElementById('catalogModal');
    const content = document.getElementById('catalog-content');
    modal.style.display = 'flex';
    content.innerHTML = '<div class="loader"></div>';

    try {
        const res = await fetch(`/chat/supplier-catalog/${currentChatUser.id}/`);
        const data = await res.json();
        if (!data.has_catalog) {
            content.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted);">
                <div style="font-size:2.5rem;margin-bottom:10px;">📭</div>
                <p>Este proveedor no ha subido su catálogo aún.</p>
            </div>`;
            return;
        }
        window.open(data.catalog_url, '_blank');
        closeCatalogModal();
    } catch (err) {
        content.innerHTML = `<p style="color:#ef4444;text-align:center;">Error: ${err.message}</p>`;
    }
}

function closeCatalogModal() {
    const modal = document.getElementById('catalogModal');
    if (modal) modal.style.display = 'none';
}

/* ===============================
   EVENTS
================================ */
function wireEvents() {
    sendBtn?.addEventListener('click', sendMessage);

    messageInput?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });

    // Auto-resize textarea
    messageInput?.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        // Toggle send button active state
        const hasText = messageInput.value.trim().length > 0;
        sendBtn?.classList.toggle('active', hasText);
    });

    fileBtn?.addEventListener('click', () => fileInput?.click());
    fileInput?.addEventListener('change', function() {
        if (!this.files || !this.files[0]) return;
        if (messageInput) messageInput.value = `📎 Archivo: ${this.files[0].name}`;
        sendBtn?.classList.add('active');
        setTimeout(sendMessage, 100);
    });

    document.getElementById('quoteBtn')?.addEventListener('click', openQuoteModal);

    document.getElementById('whatsappBtn')?.addEventListener('click', () => {
        if (!currentChatUser || conversationBlocked) return;
        const btn = document.getElementById('whatsappBtn');
        const number = btn?.dataset.whatsapp;
        if (!number) { alert('Este proveedor no ha registrado WhatsApp.'); return; }
        window.open(`https://wa.me/${number}?text=${encodeURIComponent('Hola, te contacto desde Elice')}`, '_blank');
    });

    document.getElementById('catalogBtn')?.addEventListener('click', openCatalogModal);

    // Sidebar search
    document.getElementById('sidebarSearch')?.addEventListener('input', function() {
        const q = this.value.toLowerCase().trim();
        usersList?.querySelectorAll('.user-item').forEach(item => {
            const name = (item.querySelector('.user-name')?.textContent || '').toLowerCase();
            const role = (item.querySelector('.user-role')?.textContent || '').toLowerCase();
            item.style.display = (!q || name.includes(q) || role.includes(q)) ? '' : 'none';
        });
        usersList?.querySelectorAll('.cat-label').forEach(label => {
            // Show label if any sibling user-item after it is visible
            let next = label.nextElementSibling;
            let anyVisible = false;
            while (next && !next.classList.contains('cat-label')) {
                if (next.classList.contains('user-item') && next.style.display !== 'none') anyVisible = true;
                next = next.nextElementSibling;
            }
            label.style.display = anyVisible ? '' : 'none';
        });
    });
}

window.handleKeyPress = function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
};

/* ===============================
   TYPING INDICATOR
================================ */
function showTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (!indicator) return;
    const label = document.getElementById('typingLabel');
    const isBot = currentChatUser?.username === 'elicebot';
    if (label) label.textContent = isBot ? 'EliceBot está escribiendo…' : 'Escribiendo…';
    indicator.classList.add('visible');
    if (messagesContainer) messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function hideTypingIndicator() {
    document.getElementById('typingIndicator')?.classList.remove('visible');
}