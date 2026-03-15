/**
 * ETF智能投资平台 - 公共组件库
 * 提供可复用的UI组件
 */

// ==================== 导航栏组件 ====================
class Navbar {
    constructor(options = {}) {
        this.currentPage = options.currentPage || '';
        this.container = null;
        this.init();
    }

    init() {
        this.render();
        this.attachEvents();
        this.updateUserStatus();
        
        // 监听用户状态变化
        window.ETF.userManager.onChange(() => {
            this.updateUserStatus();
        });
    }

    render() {
        const navHTML = `
            <nav class="navbar">
                <div class="nav-container">
                    <a href="index.html" class="nav-logo">
                        <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <line x1="12" y1="20" x2="12" y2="10"></line>
                            <line x1="18" y1="20" x2="18" y2="4"></line>
                            <line x1="6" y1="20" x2="6" y2="16"></line>
                        </svg>
                        <span>ETF-SCUT</span>
                    </a>
                    <ul class="nav-menu">
                        <li><a href="index.html" class="nav-link ${this.currentPage === 'index' ? 'active' : ''}">首页</a></li>
                        <li><a href="predict.html" class="nav-link ${this.currentPage === 'predict' ? 'active' : ''}">股票预测</a></li>
                        <li><a href="risk.html" class="nav-link ${this.currentPage === 'risk' ? 'active' : ''}">风险评估</a></li>
                        <li><a href="backtest.html" class="nav-link ${this.currentPage === 'backtest' ? 'active' : ''}">策略回测</a></li>
                        <li id="holdingsLink" style="display: none;"><a href="holdings.html" class="nav-link ${this.currentPage === 'holdings' ? 'active' : ''}">持股管理</a></li>
                        <li id="authButtons" style="display: flex; gap: 1rem; align-items: center;">
                            <a href="login.html" class="nav-link">登录</a>
                            <a href="register.html" class="nav-btn">注册</a>
                        </li>
                        <li id="userInfo" class="user-info" style="display: none;">
                            <div class="user-avatar" id="userAvatar"></div>
                            <span id="username" class="username"></span>
                            <button id="logoutBtn" class="btn-logout">退出</button>
                        </li>
                    </ul>
                </div>
            </nav>
        `;

        // 插入到页面顶部
        document.body.insertAdjacentHTML('afterbegin', navHTML);
        this.container = document.querySelector('.navbar');
    }

    attachEvents() {
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                if (confirm('确定要退出登录吗？')) {
                    window.ETF.userManager.logout();
                    Toast.show('已退出登录', 'success');
                    setTimeout(() => {
                        window.location.href = 'index.html';
                    }, 1000);
                }
            });
        }
    }

    updateUserStatus() {
        const authButtons = document.getElementById('authButtons');
        const userInfo = document.getElementById('userInfo');
        const holdingsLink = document.getElementById('holdingsLink');
        const userAvatar = document.getElementById('userAvatar');
        const username = document.getElementById('username');

        if (window.ETF.userManager.isLoggedIn()) {
            const userData = window.ETF.userManager.getUserData();
            authButtons.style.display = 'none';
            userInfo.style.display = 'flex';
            if (holdingsLink) {
                holdingsLink.style.display = 'block';
            }
            userAvatar.textContent = userData.username ? userData.username.charAt(0).toUpperCase() : 'U';
            if (username) {
                username.textContent = userData.username || '用户';
            }
        } else {
            authButtons.style.display = 'flex';
            userInfo.style.display = 'none';
            if (holdingsLink) {
                holdingsLink.style.display = 'none';
            }
        }
    }
}

// ==================== 页脚组件 ====================
class Footer {
    constructor() {
        this.render();
    }

    render() {
        const footerHTML = `
            <footer class="footer">
                <div class="footer-content">
                    <p>© 2026 ETF-SCUT 智能投资平台 | 华南理工大学 | 基于机器学习的量化投资系统</p>
                    <div class="footer-links">
                        <a href="#" onclick="return false;">使用条款</a>
                        <a href="#" onclick="return false;">隐私政策</a>
                        <a href="#" onclick="return false;">联系我们</a>
                    </div>
                </div>
            </footer>
        `;

        document.body.insertAdjacentHTML('beforeend', footerHTML);
    }
}

// ==================== Toast 提示组件 ====================
class Toast {
    static container = null;

    static init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    }

    static show(message, type = 'info', duration = 3000) {
        this.init();

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ⓘ'
        };

        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-message">${message}</div>
        `;

        this.container.appendChild(toast);

        // 触发动画
        setTimeout(() => toast.classList.add('show'), 10);

        // 自动移除
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);

        return toast;
    }

    static success(message, duration) {
        return this.show(message, 'success', duration);
    }

    static error(message, duration) {
        return this.show(message, 'error', duration);
    }

    static warning(message, duration) {
        return this.show(message, 'warning', duration);
    }

    static info(message, duration) {
        return this.show(message, 'info', duration);
    }
}

// ==================== Loading 加载组件 ====================
class Loading {
    static instance = null;
    static count = 0;

    static show(message = '加载中...') {
        this.count++;
        
        if (!this.instance) {
            this.instance = document.createElement('div');
            this.instance.className = 'loading-overlay';
            this.instance.innerHTML = `
                <div class="loading-spinner">
                    <div class="spinner"></div>
                    <div class="loading-text">${message}</div>
                </div>
            `;
            document.body.appendChild(this.instance);
            document.body.style.overflow = 'hidden';
        }
    }

    static hide() {
        this.count = Math.max(0, this.count - 1);
        
        if (this.count === 0 && this.instance) {
            this.instance.remove();
            this.instance = null;
            document.body.style.overflow = '';
        }
    }

    static hideAll() {
        this.count = 0;
        if (this.instance) {
            this.instance.remove();
            this.instance = null;
            document.body.style.overflow = '';
        }
    }
}

// ==================== Modal 模态框组件 ====================
class Modal {
    constructor(options = {}) {
        this.title = options.title || '';
        this.content = options.content || '';
        this.confirmText = options.confirmText || '确定';
        this.cancelText = options.cancelText || '取消';
        this.onConfirm = options.onConfirm || (() => {});
        this.onCancel = options.onCancel || (() => {});
        this.showCancel = options.showCancel !== false;
        this.element = null;
    }

    show() {
        this.render();
        this.attachEvents();
        document.body.style.overflow = 'hidden';
        
        // 触发动画
        setTimeout(() => {
            this.element.classList.add('show');
        }, 10);
    }

    hide() {
        this.element.classList.remove('show');
        setTimeout(() => {
            this.element.remove();
            document.body.style.overflow = '';
        }, 300);
    }

    render() {
        const modalHTML = `
            <div class="modal-overlay">
                <div class="modal-dialog">
                    <div class="modal-header">
                        <h3 class="modal-title">${this.title}</h3>
                        <button class="modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        ${this.content}
                    </div>
                    <div class="modal-footer">
                        ${this.showCancel ? `<button class="btn-modal btn-cancel">${this.cancelText}</button>` : ''}
                        <button class="btn-modal btn-confirm">${this.confirmText}</button>
                    </div>
                </div>
            </div>
        `;

        const temp = document.createElement('div');
        temp.innerHTML = modalHTML;
        this.element = temp.firstElementChild;
        document.body.appendChild(this.element);
    }

    attachEvents() {
        const closeBtn = this.element.querySelector('.modal-close');
        const cancelBtn = this.element.querySelector('.btn-cancel');
        const confirmBtn = this.element.querySelector('.btn-confirm');
        const overlay = this.element;

        closeBtn.addEventListener('click', () => {
            this.onCancel();
            this.hide();
        });

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.onCancel();
                this.hide();
            });
        }

        confirmBtn.addEventListener('click', () => {
            this.onConfirm();
            this.hide();
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.onCancel();
                this.hide();
            }
        });
    }

    static confirm(options) {
        return new Promise((resolve) => {
            const modal = new Modal({
                ...options,
                onConfirm: () => {
                    resolve(true);
                    if (options.onConfirm) options.onConfirm();
                },
                onCancel: () => {
                    resolve(false);
                    if (options.onCancel) options.onCancel();
                }
            });
            modal.show();
        });
    }

    static alert(options) {
        return new Modal({
            ...options,
            showCancel: false
        }).show();
    }
}

// ==================== Card 卡片组件 ====================
class Card {
    constructor(options = {}) {
        this.title = options.title || '';
        this.icon = options.icon || '';
        this.content = options.content || '';
        this.footer = options.footer || '';
        this.className = options.className || '';
        this.onClick = options.onClick;
    }

    render() {
        const card = document.createElement('div');
        card.className = `card ${this.className}`;
        
        if (this.onClick) {
            card.style.cursor = 'pointer';
            card.addEventListener('click', this.onClick);
        }

        card.innerHTML = `
            ${this.icon ? `<div class="card-icon">${this.icon}</div>` : ''}
            ${this.title ? `<h3 class="card-title">${this.title}</h3>` : ''}
            ${this.content ? `<div class="card-content">${this.content}</div>` : ''}
            ${this.footer ? `<div class="card-footer">${this.footer}</div>` : ''}
        `;

        return card;
    }
}

// ==================== 表单验证辅助 ====================
class FormValidator {
    constructor(formElement) {
        this.form = formElement;
        this.errors = {};
    }

    /**
     * 验证单个字段
     */
    validateField(name, rules) {
        const field = this.form.elements[name];
        if (!field) return true;

        const value = field.value.trim();
        this.clearFieldError(field);

        for (const rule of rules) {
            if (rule.required && !value) {
                this.setFieldError(field, rule.message || '此字段不能为空');
                return false;
            }

            if (rule.pattern && !rule.pattern.test(value)) {
                this.setFieldError(field, rule.message || '格式不正确');
                return false;
            }

            if (rule.minLength && value.length < rule.minLength) {
                this.setFieldError(field, rule.message || `最少需要${rule.minLength}个字符`);
                return false;
            }

            if (rule.maxLength && value.length > rule.maxLength) {
                this.setFieldError(field, rule.message || `最多只能${rule.maxLength}个字符`);
                return false;
            }

            if (rule.validator && !rule.validator(value)) {
                this.setFieldError(field, rule.message || '验证失败');
                return false;
            }
        }

        return true;
    }

    /**
     * 验证整个表单
     */
    validate(rules) {
        let isValid = true;
        this.errors = {};

        for (const [name, fieldRules] of Object.entries(rules)) {
            if (!this.validateField(name, fieldRules)) {
                isValid = false;
            }
        }

        return isValid;
    }

    /**
     * 设置字段错误
     */
    setFieldError(field, message) {
        this.errors[field.name] = message;
        field.classList.add('error');
        
        let errorEl = field.parentElement.querySelector('.field-error');
        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.className = 'field-error';
            field.parentElement.appendChild(errorEl);
        }
        errorEl.textContent = message;
    }

    /**
     * 清除字段错误
     */
    clearFieldError(field) {
        delete this.errors[field.name];
        field.classList.remove('error');
        
        const errorEl = field.parentElement.querySelector('.field-error');
        if (errorEl) {
            errorEl.remove();
        }
    }

    /**
     * 清除所有错误
     */
    clearAllErrors() {
        this.errors = {};
        this.form.querySelectorAll('.error').forEach(field => {
            this.clearFieldError(field);
        });
    }
}

// ==================== 导出到全局 ====================
window.ETF = window.ETF || {};
Object.assign(window.ETF, {
    Navbar,
    Footer,
    Toast,
    Loading,
    Modal,
    Card,
    FormValidator
});
