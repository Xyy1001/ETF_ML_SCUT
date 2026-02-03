// 看板娘组件JavaScript
(function () {
    // 创建看板娘HTML
    const mascotHTML = `
        <div class="mascot-container">
            <div class="mascot-avatar" id="mascotAvatar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    <path d="M8 10h.01M12 10h.01M16 10h.01" />
                </svg>
            </div>
            <div class="mascot-chat-box" id="mascotChatBox">
                <div class="mascot-header">
                    <div class="mascot-title">💬 ETF-ML小助手</div>
                    <button class="mascot-close" id="mascotClose">×</button>
                </div>
                <div class="mascot-messages" id="mascotMessages">
                    <div class="mascot-message ai">
                        <div class="mascot-message-avatar">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 2v20M2 12h20"/>
                            </svg>
                        </div>
                        <div class="mascot-message-bubble">
                            你好呀！我是ETF-ML小助手~有什么可以帮您的吗？
                        </div>
                    </div>
                </div>
                <div class="mascot-input">
                    <form class="mascot-input-form" id="mascotForm">
                        <input type="text" class="mascot-input-field" id="mascotInput" placeholder="输入消息..." autocomplete="off">
                        <button type="submit" class="mascot-send-btn">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="22" y1="2" x2="11" y2="13"/>
                                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                            </svg>
                        </button>
                    </form>
                </div>
                <div class="mascot-quick-links">
                    <a href="ai.html" class="mascot-ai-link">🤖 前往专业AI助手</a>
                </div>
            </div>
        </div>
    `;

    // 等待DOM加载完成
    document.addEventListener('DOMContentLoaded', function () {
        // 插入看板娘HTML
        const mascotWidget = document.getElementById('mascot-widget');
        if (mascotWidget) {
            mascotWidget.innerHTML = mascotHTML;

            // 动态加载样式
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'static/mascot.css';
            document.head.appendChild(link);

            // 设置事件监听
            setupMascot();
        }
    });

    function setupMascot() {
        const avatar = document.getElementById('mascotAvatar');
        const chatBox = document.getElementById('mascotChatBox');
        const closeBtn = document.getElementById('mascotClose');
        const form = document.getElementById('mascotForm');
        const input = document.getElementById('mascotInput');
        const messagesEl = document.getElementById('mascotMessages');

        // 点击头像切换聊天框
        avatar.addEventListener('click', () => {
            chatBox.classList.toggle('active');
        });

        // 关闭聊天框
        closeBtn.addEventListener('click', () => {
            chatBox.classList.remove('active');
        });

        // 提交消息
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = input.value.trim();
            if (!message) return;

            // 添加用户消息
            addMascotMessage(message, 'user');
            input.value = '';

            // 发送到服务器
            try {
                const response = await fetch('/api/mascot/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });
                const data = await response.json();

                if (data.success) {
                    addMascotMessage(data.data.message, 'ai');
                }
            } catch (error) {
                addMascotMessage('抱歉，我遇到了一些问题，请稍后再试~', 'ai');
            }
        });

        function addMascotMessage(text, type) {
            const messageHTML = `
                <div class="mascot-message ${type}">
                    <div class="mascot-message-avatar">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${type === 'ai'
                    ? '<path d="M12 2v20M2 12h20"/>'
                    : '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'
                }
                        </svg>
                    </div>
                    <div class="mascot-message-bubble">${text}</div>
                </div>
            `;
            messagesEl.insertAdjacentHTML('beforeend', messageHTML);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
    }
})();
