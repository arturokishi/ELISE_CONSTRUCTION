
        console.log("JS LOADED");
    
        /* ===============================
           GLOBAL STATE
        ================================ */
        let currentChatUser = null;
        let currentConversationId = null;
        let csrftoken = null;
        let messageRefreshInterval = null;
        let conversationBlocked = false;
        
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
            console.log("DOM fully loaded");
            
            // Get CSRF token
            const metaTag = document.querySelector('meta[name="csrf-token"]');
            if (metaTag) {
                csrftoken = metaTag.getAttribute('content');
            }
        
            // Cache DOM elements
            usersList = document.getElementById('usersList');
            messagesContainer = document.getElementById('messagesContainer');
            messageInput = document.getElementById('messageInput');
            sendBtn = document.getElementById('sendBtn');
            fileBtn = document.getElementById('fileBtn');
            fileInput = document.getElementById('fileInput');
            messageInputContainer = document.getElementById('messageInputContainer');
            currentUserName = document.getElementById('currentUserName');
            currentUserInfo = document.getElementById('currentUserInfo');
            currentUserAvatar = document.getElementById('currentUserAvatar');
        
            // Check if all elements exist
            if (!usersList || !messagesContainer || !messageInput || !sendBtn) {
                console.error("Critical DOM elements missing!");
                return;
            }
        
            wireEvents();
            loadUsers();
        
            const conversationId = getQueryParam('conversation');
            if (conversationId) {
                selectConversationById(conversationId);
            }
        });
        
        /* ===============================
           HELPERS
        ================================ */
        function getQueryParam(name) {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get(name);
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
                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                const data = await res.json();
        
                if (!data.users || !data.users.length) {
                    usersList.innerHTML = `
                        <div style="padding:20px;color:#9ca3af;text-align:center">
                            No hay otros usuarios registrados
                        </div>`;
                    return;
                }
        
                displayUsers(data.users);
        
            } catch (error) {
                console.error("Error loading users:", error);
                usersList.innerHTML = `
                    <div style="padding:20px;color:#ef4444;text-align:center">
                        Error cargando usuarios: ${error.message}
                    </div>`;
            }
        }
        
        /* ===============================
           DISPLAY USERS - FIXED (NO DUPLICATES)
        =============================== */
        function displayUsers(users) {
            if (!usersList) return;
            usersList.innerHTML = '';
            
            // Define role groups in Spanish
            const groups = {
                'client': 'Clientes',
                'supplier': 'Proveedores',
                'admin': 'Administradores',
                'staff': 'Personal'
            };
            
            // Check current user role from the page
            const isClient = document.body.dataset.userRole === 'client';
            
            if (isClient) {
                // Separate bot from regular suppliers
                const botUsers = users.filter(user => user.is_bot);
                const supplierUsers = users.filter(user => !user.is_bot);
                
                // Remove duplicate suppliers by ID
                const uniqueSuppliers = [];
                const seenSupplierIds = new Set();
                
                supplierUsers.forEach(user => {
                    if (!seenSupplierIds.has(user.id)) {
                        seenSupplierIds.add(user.id);
                        uniqueSuppliers.push(user);
                    }
                });
                
                console.log(`Original suppliers: ${supplierUsers.length}, Unique: ${uniqueSuppliers.length}`);
                
                // Display bot first (if exists) - also deduplicate bot
                if (botUsers.length > 0) {
                    const uniqueBot = [];
                    const seenBotIds = new Set();
                    
                    botUsers.forEach(user => {
                        if (!seenBotIds.has(user.id)) {
                            seenBotIds.add(user.id);
                            uniqueBot.push(user);
                        }
                    });
                    
                    if (uniqueBot.length > 0) {
                        const botHeader = document.createElement('h3');
                        botHeader.textContent = '🤖 Asistente';
                        botHeader.style.marginTop = '0';
                        botHeader.style.color = '#9ca3af';
                        usersList.appendChild(botHeader);
                        
                        uniqueBot.forEach(user => {
                            const userItem = createUserItem(user);
                            usersList.appendChild(userItem);
                        });
                    }
                }
                
                // Group suppliers by their product categories
                const suppliersByCategory = {};
                const categoryUserMap = new Map(); // Track which users are already in which category
                
                uniqueSuppliers.forEach(user => {
                    if (user.categories && user.categories.length > 0) {
                        // Remove duplicate categories for the same user
                        const uniqueCategories = [...new Set(user.categories)];
                        
                        uniqueCategories.forEach(category => {
                            if (!suppliersByCategory[category]) {
                                suppliersByCategory[category] = [];
                                categoryUserMap.set(category, new Set());
                            }
                            
                            // Check if this user is already in this category
                            if (!categoryUserMap.get(category).has(user.id)) {
                                categoryUserMap.get(category).add(user.id);
                                suppliersByCategory[category].push(user);
                            }
                        });
                    } else {
                        // Suppliers with no categories go to "Otros"
                        const category = 'Otros';
                        if (!suppliersByCategory[category]) {
                            suppliersByCategory[category] = [];
                            categoryUserMap.set(category, new Set());
                        }
                        
                        if (!categoryUserMap.get(category).has(user.id)) {
                            categoryUserMap.get(category).add(user.id);
                            suppliersByCategory[category].push(user);
                        }
                    }
                });
                
                // Display categories and their suppliers
                Object.keys(suppliersByCategory).sort().forEach(category => {
                    // Only show category if it has suppliers
                    if (suppliersByCategory[category].length > 0) {
                        const categoryHeader = document.createElement('h3');
                        categoryHeader.textContent = category;
                        categoryHeader.style.marginTop = '15px';
                        categoryHeader.style.color = '#fbbf24';
                        usersList.appendChild(categoryHeader);
                        
                        suppliersByCategory[category].forEach(user => {
                            const userItem = createUserItem(user);
                            usersList.appendChild(userItem);
                        });
                    }
                });
                
            } else {
                // For suppliers: Show all users grouped by role - with deduplication
                const groupedUsers = {};
                const seenUserIds = new Set();
                
                users.forEach(user => {
                    if (!seenUserIds.has(user.id)) {
                        seenUserIds.add(user.id);
                        const role = user.role || 'client';
                        if (!groupedUsers[role]) {
                            groupedUsers[role] = [];
                        }
                        groupedUsers[role].push(user);
                    }
                });
                
                // Display each role group
                Object.keys(groups).forEach(roleKey => {
                    const roleUsers = groupedUsers[roleKey];
                    if (!roleUsers || roleUsers.length === 0) return;
                    
                    const header = document.createElement('h3');
                    header.textContent = groups[roleKey];
                    usersList.appendChild(header);
                    
                    roleUsers.forEach(user => {
                        const userItem = createUserItem(user);
                        usersList.appendChild(userItem);
                    });
                });
            }
            
            // Add click handlers
            document.querySelectorAll('.user-item').forEach(item => {
                item.addEventListener('click', function(e) {
                    document.querySelectorAll('.user-item').forEach(i => {
                        i.classList.remove('active');
                    });
                    this.classList.add('active');
                    
                    const userId = this.dataset.userId;
                    if (userId) {
                        selectUser(userId);
                    }
                });
            });
        }
        
        /* ===============================
           CREATE USER ITEM - FIXED (NO DUPLICATE CATEGORIES)
        =============================== */
        function createUserItem(user) {
            const name = (user.first_name && user.last_name)
                ? `${user.first_name} ${user.last_name}`
                : user.username;
            
            // Use different avatar color for bot
            const avatarColor = user.is_bot ? '#9ca3af' : (user.avatar_color || '#fbbf24');
            const initial = user.is_bot ? '🤖' : name.charAt(0).toUpperCase();
            const role = user.is_bot ? 'Bot' : (user.role_display || user.role || 'Usuario');
            const company = user.company ? `<div class="user-role">${user.company}</div>` : '';
            
            // Add category badges if they exist (for suppliers) - ensure no duplicates
            let categoryHtml = '';
            if (!user.is_bot && user.categories && user.categories.length > 0) {
                // Remove duplicate categories
                const uniqueCategories = [...new Set(user.categories)];
                
                categoryHtml = '<div style="display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px;">';
                uniqueCategories.slice(0, 2).forEach(cat => {
                    categoryHtml += `<span style="font-size: 10px; background: #fbbf24; color: #1f2933; padding: 2px 6px; border-radius: 10px;">${cat}</span>`;
                });
                if (uniqueCategories.length > 2) {
                    categoryHtml += `<span style="font-size: 10px; color: #9ca3af;">+${uniqueCategories.length-2}</span>`;
                }
                categoryHtml += '</div>';
            }
            
            // Add bot badge
            let botBadge = '';
            if (user.is_bot) {
                botBadge = '<span style="font-size: 10px; background: #9ca3af; color: white; padding: 2px 6px; border-radius: 10px; margin-left: 5px;">Bot</span>';
            }
            
            const item = document.createElement('div');
            item.className = 'user-item';
            item.dataset.userId = user.id;
            
            item.innerHTML = `
                <div class="user-avatar" style="background:${avatarColor}">
                    ${initial}
                </div>
                <div class="user-info">
                    <div class="user-name">
                        ${escapeHtml(name)}${botBadge}
                        <span class="status-indicator ${user.is_bot ? 'status-offline' : 'status-online'}"></span>
                    </div>
                    <div class="user-role">${escapeHtml(role)}</div>
                    ${company}
                    ${categoryHtml}
                </div>
            `;
            
            return item;
        }
        
        /* ===============================
           SELECT USER - UPDATED WITH QUOTE BUTTON
        ================================ */
        async function selectUser(userId) {
            if (!userId) return;

            // Limpiar estado anterior
            currentChatUser = null;
            currentConversationId = null;
            messagesContainer.innerHTML = '';
            setConversationState(true);
            
            // Clear any existing refresh interval
            if (messageRefreshInterval) {
                clearInterval(messageRefreshInterval);
                messageRefreshInterval = null;
            }
            
            try {
                const res = await fetch(`/chat/conversation/${userId}/`);
                if (!res.ok) {
                    // Handle 403 Forbidden specifically
                    if (res.status === 403) {
                        const errorData = await res.json();
                        messagesContainer.innerHTML = `
                            <div style="text-align: center; padding: 40px; color: #ef4444;">
                                <div style="font-size: 24px; margin-bottom: 10px;">🚫</div>
                                <h3>No puedes chatear con este usuario</h3>
                                <p>${errorData.error || 'Debes solicitar una cotización primero.'}</p>
                            </div>
                        `;
                        if (messageInputContainer) {
                            messageInputContainer.style.display = 'none';
                        }

                        currentChatUser = null;
                        currentConversationId = null;
                        setConversationState(true);

                        return;
                    }


                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                
                const data = await res.json();
        
                if (!data.other_user) {
                    console.error("No user data returned");
                    return;
                }
        
                currentChatUser = data.other_user;
                currentConversationId = data.conversation_id;
        
                updateChatHeader(data.other_user);
                displayMessages(data.messages || []);

                // Mensaje de bienvenida del bot al abrir por primera vez
                const isBot = data.other_user.username === 'elicebot';
                const noMessages = !data.messages || data.messages.length === 0;
                if (isBot && noMessages) {
                    setTimeout(() => {
                        appendMessage({
                            content: "Hola 👋 soy el chatbot de Elice 🤖\n\nAquí puedo ayudarte a conectar con proveedores de materiales de construcción.\n\nSolo escríbeme el material que necesitas y te conecto:\n• Vidrio\n• Aluminio\n• Acero\n• Pintura\n• Cemento",
                            is_sent: false,
                            timestamp: formatTime()
                        });
                    }, 500);
                }
        
                if (messageInputContainer) {
                    messageInputContainer.style.display = 'flex';
                }
        
                // Enable quote, call, video buttons
                setConversationState(false);

                console.log('DEBUG selectUser success:');
                console.log('  other_user:', data.other_user);
                console.log('  role:', data.other_user.role);
                console.log('  conversationBlocked:', conversationBlocked);

            const quoteBtn = document.getElementById('quoteBtn');
                if (quoteBtn) {
                    const isSupplier = data.other_user.role === 'supplier';
                    console.log('  isSupplier:', isSupplier);
                    console.log('  quoteBtn.disabled will be:', !isSupplier);
                    quoteBtn.disabled = !isSupplier;
                }

                // WhatsApp button
                const whatsappBtn = document.getElementById('whatsappBtn');
                if (whatsappBtn) {
                    const hasWhatsapp = data.other_user.role === 'supplier' && data.other_user.whatsapp;
                    whatsappBtn.disabled = !hasWhatsapp;
                    whatsappBtn.dataset.whatsapp = data.other_user.whatsapp || '';
                }

                // Catalog button
                const catalogBtn = document.getElementById('catalogBtn');
                if (catalogBtn) {
                    const hasCatalog = data.other_user.role === 'supplier' && data.other_user.has_catalog;
                    catalogBtn.style.display = hasCatalog ? 'inline-block' : 'none';
                    catalogBtn.disabled = !hasCatalog;
                }
                                
                // Start periodic refresh for new messages (every 5 seconds)
                startMessageRefresh();
        
            } catch (error) {
                console.error("Select user error:", error);
                messagesContainer.innerHTML = `
                    <div style="text-align: center; padding: 40px; color: #ef4444;">
                        <div style="font-size: 24px; margin-bottom: 10px;">❌</div>
                        <h3>Error al cargar la conversación</h3>
                        <p>${error.message}</p>
                    </div>
                `;
            }
        }
        
        /* ===============================
           SELECT BY CONVERSATION ID
        ================================ */
        async function selectConversationById(conversationId) {
            if (!conversationId) return;
            
            // Clear any existing refresh interval
            if (messageRefreshInterval) {
                clearInterval(messageRefreshInterval);
                messageRefreshInterval = null;
            }
            
            try {
                const res = await fetch(`/chat/conversation/by-id/${conversationId}/`);
                if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
                
                const data = await res.json();
        
                if (!data.success) return;
        
                currentChatUser = data.other_user;
                currentConversationId = conversationId;
        
                updateChatHeader(data.other_user);
                displayMessages(data.messages || []);
        
                if (messageInputContainer) {
                    messageInputContainer.style.display = 'flex';
                }
                
                // Start periodic refresh for new messages
                startMessageRefresh();
        
            } catch (error) {
                console.error("Conversation load error:", error);
            }
        }
        
        
        
        /* ===============================
           HEADER & MESSAGES
        ================================ */
        function updateChatHeader(user) {
            if (!user) return;
            
            const name = (user.first_name && user.last_name)
                ? `${user.first_name} ${user.last_name}`
                : user.username;
        
            if (currentUserName) currentUserName.textContent = name;
            if (currentUserAvatar) currentUserAvatar.textContent = name.charAt(0).toUpperCase();
            
            let infoText = user.role_display || user.role || '';
            if (user.company) infoText += ` • ${user.company}`;
            
            if (currentUserInfo) currentUserInfo.innerHTML = escapeHtml(infoText);
        }
        
        function displayMessages(messages) {
            if (!messagesContainer) return;
            
            messagesContainer.innerHTML = '';
        
            if (!messages || messages.length === 0) {
                messagesContainer.innerHTML = `
                    <div style="padding:40px;text-align:center;color:#9ca3af">
                        No hay mensajes. Comienza la conversación para conectar con proveedores!
                    </div>`;
                return;
            }
        
            messages.forEach(msg => appendMessage(msg, false));
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function appendMessage(message, shouldScroll = true) {
    if (!messagesContainer) return;

    // Check for duplicates by message ID if available, else fallback to content+sent
    const existingMessages = messagesContainer.querySelectorAll('.message');
    for (let i = 0; i < existingMessages.length; i++) {
        const msgDiv = existingMessages[i];
        const msgId = msgDiv.dataset.messageId;
        const content = msgDiv.querySelector('.message-content')?.textContent;
        const isSent = msgDiv.classList.contains('sent') === message.is_sent;

        if ((message.id && msgId === String(message.id)) || (!message.id && content === message.content && isSent)) {
            return; // Skip duplicate
        }
    }

    const div = document.createElement('div');
    div.className = `message ${message.is_sent ? 'sent' : 'received'}`;
    if (message.id) div.dataset.messageId = message.id;

    div.innerHTML = `
        <div class="message-content">
            ${escapeHtml(message.content)}
        </div>
        <div class="message-time">
            ${message.timestamp || formatTime()}
        </div>
    `;

    messagesContainer.appendChild(div);

    if (shouldScroll) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

        /* ===============================
           MESSAGE REFRESH
        ================================ */
        function startMessageRefresh() {
            if (messageRefreshInterval) {
                clearInterval(messageRefreshInterval);
            }
            // Refresh messages every 5 seconds
            messageRefreshInterval = setInterval(refreshMessages, 5000);
        }
        
        async function refreshMessages() {
    if (!currentConversationId) return;

    try {
        const res = await fetch(`/chat/conversation/by-id/${currentConversationId}/`);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

        const data = await res.json();

        if (data.messages && messagesContainer) {
            const wasAtBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop <= messagesContainer.clientHeight + 100;

            // Solo agrega mensajes nuevos, no limpiar todo
            data.messages.forEach(msg => appendMessage(msg, false));

            if (wasAtBottom) {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        }
    } catch (error) {
        console.error("Refresh error:", error);
    }
}
        
        /* ===============================
           SEND MESSAGE - IMPROVED VERSION
        ================================ */
        async function sendMessage() {
            if (!messageInput) return;
            
            const content = messageInput.value.trim();
            if (!content || !currentChatUser) return;
        
            // Store the message to check for duplicates
            const sentContent = content;
        
         const tempId = 'temp-' + Date.now();
appendMessage({
    id: tempId,
    content: content,
    is_sent: true,
    timestamp: formatTime()
});

// Guarda referencia al elemento temporal
const tempMsg = messagesContainer.querySelector(`[data-message-id="${tempId}"]`);
        
            messageInput.value = '';
        
            try {
                const res = await fetch('/chat/send/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken
    },
    body: JSON.stringify({
        user_id: currentChatUser.id,
        content: content,
        conversation_id: currentConversationId
    })
});

if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `HTTP error! status: ${res.status}`);
}

const data = await res.json();

// ✅ Reemplaza el tempId con el ID real del servidor
if (data.message_id && tempMsg) {
    tempMsg.dataset.messageId = String(data.message_id);
}

// If bot replied, show it after a short delay
if (data.bot_reply) {
    setTimeout(() => {
        appendMessage({
            id: data.bot_reply_id,
            content: data.bot_reply,
            is_sent: false,
            timestamp: formatTime()
        });
    }, 500);
}
                
                // Also refresh messages from server to ensure sync
                // Short delay to let server process
                // setTimeout(refreshMessages, 300);
        
            } catch (error) {
                console.error("Send message error:", error);
                appendMessage({
                    content: `❌ Error al enviar mensaje: ${error.message}`,
                    is_sent: true,
                    timestamp: formatTime()
                });
            }
        }
        
        /* ===============================
           QUOTE FORM FUNCTIONS
        ================================ */
        
        // Load dynamic quote form - ENHANCED DEBUG VERSION
        async function loadQuoteForm() {
            if (!currentChatUser) {
                alert('Selecciona un usuario primero');
                return;
            }
            
            console.log('🔍 Loading quote form for user:', currentChatUser);
            console.log('🔍 User ID:', currentChatUser.id);
            console.log('🔍 User role:', currentChatUser.role);
            
            const modal = document.getElementById('quoteModal');
            const loading = document.getElementById('quote-form-loading');
            const container = document.getElementById('quote-form-container');
            const supplierName = document.getElementById('supplier-name');
            
            if (!modal || !loading || !container || !supplierName) {
                console.error('❌ Modal elements not found!');
                alert('Error: Elementos del modal no encontrados');
                return;
            }
            
            modal.style.display = 'flex';
            loading.style.display = 'block';
            loading.innerHTML = '<div class="loader"></div><p>Cargando productos...</p>';
            container.style.display = 'none';
            
            try {
                const url = `/chat/quote-form/${currentChatUser.id}/`;
                console.log('🔍 Fetching from:', url);
                
                const response = await fetch(url);
                console.log('🔍 Response status:', response.status);
                console.log('🔍 Response OK?', response.ok);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('❌ Error response:', errorText);
                    loading.innerHTML = `<p style="color: #ef4444;">❌ Error ${response.status}: ${errorText.substring(0, 100)}</p>`;
                    return;
                }
                
                const data = await response.json();
                console.log('🔍 Received data:', data);
                
                if (data.error) {
                    console.error('❌ API error:', data.error);
                    loading.innerHTML = `<p style="color: #ef4444;">❌ Error: ${data.error}</p>`;
                    return;
                }
                
                // Check if we have categories
                if (!data.categories || data.categories.length === 0) {
                    console.warn('⚠️ No categories or products found');
                    loading.innerHTML = `
                        <div style="text-align:center; padding:20px;">
                            <div style="font-size:36px; margin-bottom:12px;">📋</div>
                            <p style="font-weight:600; color:#1f2933; margin-bottom:10px;">
                                Este proveedor cotiza directamente por chat o WhatsApp.
                            </p>
                            <p style="color:#6b7280; font-size:14px; margin-bottom:20px;">
                                No tiene productos configurados en la plataforma, pero puedes:
                            </p>
                            <div style="text-align:left; display:inline-block; margin-bottom:20px;">
                                <p style="margin-bottom:8px;">📄 Revisa su catálogo presionando el botón <strong>📄</strong> en la parte superior</p>
                                <p style="margin-bottom:8px; margin-top:12px;"><strong>¿Listo para cotizar?</strong></p>
                                <p style="margin-bottom:8px;">1. 🗨️ Escríbele directamente en este chat</p>
                                <p style="margin-bottom:8px;">2. 💬 Contáctalo por WhatsApp con el botón <strong>💬</strong> arriba</p>
                            </div>
                            <br>
                            <button onclick="closeQuoteModal()" 
                                style="background:#1f2933;color:white;border:none;padding:10px 24px;
                                       border-radius:5px;cursor:pointer;font-size:14px;">
                                ← Volver al chat
                            </button>
                        </div>`;
                    return;
                }
                
                console.log(`✅ Found ${data.categories.length} categories`);
                
                supplierName.textContent = `Proveedor: ${data.supplier.name}`;
                
                // Populate product dropdown
                const productSelect = document.getElementById('quote-product');
                if (!productSelect) {
                    console.error('❌ Product select element not found');
                    return;
                }
                
                productSelect.innerHTML = '<option value="">Selecciona un producto</option>';
                
                let productCount = 0;
                data.categories.forEach(category => {
                    if (category.products && category.products.length > 0) {
                        const optgroup = document.createElement('optgroup');
                        optgroup.label = category.name;
                        
                        category.products.forEach(product => {
                            productCount++;
                            const option = document.createElement('option');
                            option.value = JSON.stringify({
                                id: product.id,
                                name: product.name,
                                price: product.base_price,
                                unit: product.unit,
                                options: product.options || []
                            });
                            option.textContent = `${product.name} - $${product.base_price} por ${product.unit}`;
                            optgroup.appendChild(option);
                        });
                        
                        productSelect.appendChild(optgroup);
                    }
                });
        
                if (productCount === 0) {
                    console.warn('⚠️ No products found in categories');
                    loading.innerHTML = '<p style="color: #f59e0b;">⚠️ Este proveedor no tiene productos activos.</p>';
                    return;
                }
                
                console.log(`✅ Loaded ${productCount} products`);
                loading.style.display = 'none';
                container.style.display = 'block';
                
            } catch (error) {
                console.error('❌ Error loading form:', error);
                loading.innerHTML = `<p style="color: #ef4444;">❌ Error: ${error.message}</p>`;
            }
        }
        
        // Handle product selection change
        document.getElementById('quote-product')?.addEventListener('change', function(e) {
            const optionsContainer = document.getElementById('product-options-container');
            optionsContainer.innerHTML = '';
            
            if (!this.value) return;
            
            const product = JSON.parse(this.value);
            
            product.options.forEach(opt => {
                const div = document.createElement('div');
                div.className = 'form-group';
                div.innerHTML = `
                    <label>${opt.name} ${opt.required ? '*' : ''}</label>
                    <select id="opt-${opt.name}" class="message-input" ${opt.required ? 'required' : ''}>
                        <option value="">Selecciona...</option>
                        ${opt.options.map(o => `<option value="${o}">${o}</option>`).join('')}
                    </select>
                `;
                optionsContainer.appendChild(div);
            });
        });

        function setConversationState(blocked) {
            conversationBlocked = blocked;
            const quoteBtn = document.getElementById('quoteBtn');
            const whatsappBtn = document.getElementById('whatsappBtn');
            const catalogBtn = document.getElementById('catalogBtn');
            const sendBtn = document.getElementById('sendBtn');
            const messageInput = document.getElementById('messageInput');

            if (blocked) {
                if (quoteBtn) quoteBtn.disabled = true;
                if (whatsappBtn) whatsappBtn.disabled = true;
                if (catalogBtn) catalogBtn.disabled = true;
                if (sendBtn) sendBtn.disabled = true;
                if (messageInput) messageInput.disabled = true;
                if (messageInputContainer) messageInputContainer.style.display = 'none';
            } else {
                if (quoteBtn) quoteBtn.disabled = false;
                if (whatsappBtn) whatsappBtn.disabled = false;
                if (sendBtn) sendBtn.disabled = false;
                if (messageInput) messageInput.disabled = false;
                if (messageInputContainer) messageInputContainer.style.display = 'flex';
            }
        }

        // Open quote modal
        function openQuoteModal() {
            if (conversationBlocked || !currentChatUser || !currentConversationId) {
                alert('❌ No puedes cotizar en esta conversación.\nHabla con el chatbot para conectarte con este proveedor.');
                return;
            }
            loadQuoteForm();
        }

        // Close quote modal
        function closeQuoteModal() {
            document.getElementById('quoteModal').style.display = 'none';
            document.getElementById('dynamicQuoteForm').reset();
            document.getElementById('product-options-container').innerHTML = '';
        }

        // Submit dynamic quote
        async function submitDynamicQuote() {
            const productSelect = document.getElementById('quote-product');
            if (!productSelect.value) {
                alert('Selecciona un producto');
                return;
            }
            
            const productData = JSON.parse(productSelect.value);
            const quantity = document.getElementById('quote-quantity').value;
            const notes = document.getElementById('quote-notes').value;
            
            // Collect options
            const options = {};
            productData.options.forEach(opt => {
                const select = document.getElementById(`opt-${opt.name}`);
                if (select && select.value) {
                    options[opt.name] = select.value;
                }
            });
            
            const quoteData = {
                product_id: productData.id,
                product_name: productData.name,
                quantity: parseInt(quantity),
                options: options,
                notes: notes,
                estimated_total: productData.price * quantity
            };
            
            // Send to chat
            const message = formatQuoteMessage(quoteData, currentChatUser);
            
            try {
                const res = await fetch('/chat/send/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken
                    },
                    body: JSON.stringify({
                        user_id: currentChatUser.id,
                        content: message,
                        conversation_id: currentConversationId
                    })
                });
                
                if (res.ok) {
                    alert('✅ Cotización enviada correctamente');
                    closeQuoteModal();
                    refreshMessages();
                } else {
                    throw new Error('Error al enviar');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('❌ Error al enviar la cotización');
            }
        }

        function formatQuoteMessage(data, supplier) {
            const options = Object.entries(data.options)
                .map(([k, v]) => `  • ${k}: ${v}`).join('\n');
            
            return `📋 **NUEVA SOLICITUD DE COTIZACIÓN**\n` +
                `━━━━━━━━━━━━━━━━━━━━━━━\n` +
                `**Producto:** ${data.product_name}\n` +
                `**Cantidad:** ${data.quantity}\n` +
                `${options ? `**Especificaciones:**\n${options}\n` : ''}` +
                `**Total estimado:** $${data.estimated_total}\n` +
                `**Notas:** ${data.notes || 'Ninguna'}\n` +
                `━━━━━━━━━━━━━━━━━━━━━━━\n` +
                `_Enviado a: ${supplier.username}_`;
        }
        
        /* ===============================
           EVENTS - UPDATED WITH QUOTE BUTTON
        ================================ */
        function wireEvents() {
            if (sendBtn) {
                sendBtn.addEventListener('click', sendMessage);
            }
        
            if (messageInput) {
                messageInput.addEventListener('keypress', e => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        sendMessage();
                    }
                });
            }
        
            if (fileBtn && fileInput) {
                fileBtn.addEventListener('click', () => fileInput.click());
        
                fileInput.addEventListener('change', function(e) {
                    if (!this.files || !this.files[0]) return;
                    
                    const fileName = this.files[0].name;
                    if (messageInput) {
                        messageInput.value = `📎 Archivo: ${fileName}`;
                    }
                    // Optional: auto-send after brief delay
                    setTimeout(sendMessage, 100);
                });
            }
        
            // Quote button
            const quoteBtn = document.getElementById('quoteBtn');
            if (quoteBtn) {
                quoteBtn.addEventListener('click', openQuoteModal);
            }
        
            // WhatsApp button
            const whatsappBtn = document.getElementById('whatsappBtn');
            if (whatsappBtn) {
                whatsappBtn.addEventListener('click', () => {
                    if (!currentChatUser || conversationBlocked) return;
                    const number = whatsappBtn.dataset.whatsapp;
                    if (!number) {
                        alert('Este proveedor no ha registrado su número de WhatsApp.');
                        return;
                    }
                    const message = encodeURIComponent('Hola, te contacto desde Elice');
                    window.open(`https://wa.me/${number}?text=${message}`, '_blank');
                });
            }

            // Catalog button
            const catalogBtn = document.getElementById('catalogBtn');
            if (catalogBtn) {
                catalogBtn.addEventListener('click', openCatalogModal);
            }
        }
        
        // Make handleKeyPress available globally if used in onkeypress attribute
        window.handleKeyPress = function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        };

        async function openCatalogModal() {
            if (!currentChatUser || conversationBlocked) return;

            const modal = document.getElementById('catalogModal');
            const content = document.getElementById('catalog-content');
            const downloadBtn = document.getElementById('catalog-download-btn');

            modal.style.display = 'flex';
            content.innerHTML = '<div class="loader"></div><p style="text-align:center">Cargando catálogo...</p>';
            downloadBtn.style.display = 'none';

            try {
                const res = await fetch(`/chat/supplier-catalog/${currentChatUser.id}/`);
                const data = await res.json();

                if (!data.has_catalog) {
                    content.innerHTML = `
                        <div style="text-align:center; padding:30px; color:#9ca3af;">
                            <div style="font-size:40px; margin-bottom:10px;">📭</div>
                            <p>Este proveedor no ha subido un catálogo todavía.</p>
                        </div>`;
                    return;
                }

                window.open(data.catalog_url, '_blank');
                closeCatalogModal();

            } catch (error) {
                content.innerHTML = `<p style="color:#ef4444; text-align:center;">❌ Error al cargar el catálogo: ${error.message}</p>`;
            }
        }

        function closeCatalogModal() {
            const modal = document.getElementById('catalogModal');
            if (modal) modal.style.display = 'none';
        }