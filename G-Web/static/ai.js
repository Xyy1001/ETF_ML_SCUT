// AI助手页面交互
document.addEventListener('DOMContentLoaded', function () {
    loadKnowledge();
    loadSuggestions();
    setupChat();
});

async function loadKnowledge() {
    const res = await fetch('/api/ai/knowledge');
    const data = await res.json();
    if (data.success) {
        const list = document.getElementById('knowledgeList');
        list.innerHTML = data.data.map(cat => `
            <div class="knowledge-item" onclick="askCategory('${cat.name}')">
                <div class="knowledge-name">${cat.name}</div>
                <div class="knowledge-preview">${cat.preview}</div>
            </div>
        `).join('');
    }
}

async function loadSuggestions() {
    const res = await fetch('/api/ai/suggest');
    const data = await res.json();
    if (data.success) {
        const list = document.getElementById('suggestionsList');
        list.innerHTML = data.data.map(q => `
            <button class="suggestion-btn" onclick="askQuestion('${q}')">${q}</button>
        `).join('');
    }
}

function setupChat() {
    document.getElementById('chatForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        input.value = '';

        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, type: 'general' })
        });
        const data = await res.json();
        if (data.success) {
            addMessage(data.data.message, 'ai');
        }
    });
}

function addMessage(text, type) {
    const messagesEl = document.getElementById('chatMessages');
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    const messageHTML = `
        <div class="message ${type}-message">
            <div class="message-avatar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${type === 'ai' ? '<path d="M12 2v20M2 12h20"/>' : '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'}
                </svg>
            </div>
            <div class="message-content">
                <div class="message-text">${text}</div>
                <div class="message-time">${time}</div>
            </div>
        </div>
    `;
    messagesEl.insertAdjacentHTML('beforeend', messageHTML);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function askQuestion(question) {
    document.getElementById('chatInput').value = question;
    document.getElementById('chatForm').dispatchEvent(new Event('submit'));
}

function askCategory(category) {
    askQuestion(`请介绍${category}`);
}

function clearChat() {
    const messagesEl = document.getElementById('chatMessages');
    messagesEl.innerHTML = `
        <div class="message ai-message">
            <div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M2 12h20"/></svg></div>
            <div class="message-content">
                <div class="message-text">聊天记录已清空。有什么可以帮您的吗？</div>
                <div class="message-time">刚刚</div>
            </div>
        </div>
    `;
}
