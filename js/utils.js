/**
 * ETF智能投资平台 - 工具函数库
 * 提供API调用、状态管理、数据处理等通用功能
 */

// ==================== API 配置 ====================
const API_CONFIG = {
    BASE_URL: (typeof window !== 'undefined' && /^https?:/i.test(window.location.protocol))
        ? window.location.origin
        : 'http://localhost:5000',
    TIMEOUT: 30000,
    ENDPOINTS: {
        // 用户相关
        USER_REGISTER: '/api/users/register',
        USER_LOGIN: '/api/users/login',
        USER_LOGOUT: '/api/users/logout',
        USER_INFO: '/api/users/info',
        
        // 预测相关
        PREDICT: '/api/predict',
        PREDICT_BATCH: '/api/predict/batch',
        PREDICT_HISTORY: '/api/predict/history',
        
        // 风险相关
        RISK_ANALYZE: '/api/risk/analyze',
        RISK_OPTIMIZE: '/api/risk/optimize',
        
        // 数据相关
        STOCK_DATA: '/api/data/stock',
        STOCK_LIST: '/api/data/stocks',
    }
};

// ==================== HTTP 请求封装 ====================
class HttpClient {
    constructor(config) {
        this.baseURL = config.BASE_URL;
        this.timeout = config.TIMEOUT;
    }

    /**
     * 通用请求方法
     * @param {string} url - 请求URL
     * @param {object} options - 请求配置
     * @returns {Promise<object>} 响应数据
     */
    async request(url, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(this.baseURL + url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...this.getAuthHeaders(),
                    ...options.headers,
                },
                credentials: 'include'
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
                throw new Error(errorData.message || `HTTP Error: ${response.status}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('请求超时，请稍后重试');
            }
            throw error;
        }
    }

    /**
     * 获取认证头
     */
    getAuthHeaders() {
        const token = localStorage.getItem('authToken');
        let currentUsername = '';
        try {
            const rawUserData = localStorage.getItem('userData');
            if (rawUserData) {
                const parsed = JSON.parse(rawUserData);
                currentUsername = (parsed && parsed.username) ? String(parsed.username).trim() : '';
            }
        } catch (error) {
            console.warn('解析 userData 失败，忽略当前用户请求头:', error);
        }

        const headers = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        if (currentUsername) {
            headers['X-Current-User'] = currentUsername;
        }
        return headers;
    }

    /**
     * GET 请求
     */
    async get(url, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;
        return this.request(fullUrl, { method: 'GET' });
    }

    /**
     * POST 请求
     */
    async post(url, data = {}) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * PUT 请求
     */
    async put(url, data = {}) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    /**
     * DELETE 请求
     */
    async delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
}

// 创建全局HTTP客户端实例
const http = new HttpClient(API_CONFIG);

// ==================== 用户状态管理 ====================
class UserManager {
    constructor() {
        this.userData = null;
        this.callbacks = [];
    }

    /**
     * 初始化用户状态
     */
    init() {
        const userData = localStorage.getItem('userData');
        if (userData) {
            try {
                this.userData = JSON.parse(userData);
                this.notifyCallbacks();
            } catch (e) {
                console.error('用户数据解析失败:', e);
                this.logout();
            }
        }
    }

    /**
     * 登录
     */
    async login(username, password) {
        try {
            const response = await http.post(API_CONFIG.ENDPOINTS.USER_LOGIN, {
                username,
                password
            });

            if (response.code === 0 && response.data) {
                this.userData = response.data;
                localStorage.setItem('userData', JSON.stringify(response.data));
                if (response.token) {
                    localStorage.setItem('authToken', response.token);
                }
                this.notifyCallbacks();
                return { success: true, message: '登录成功' };
            } else {
                return { success: false, message: response.message || '登录失败' };
            }
        } catch (error) {
            console.error('登录错误:', error);
            return { success: false, message: '登录失败：' + error.message };
        }
    }

    /**
     * 注册
     */
    async register(userData) {
        try {
            const response = await http.post(API_CONFIG.ENDPOINTS.USER_REGISTER, userData);
            return {
                success: response.code === 0,
                message: response.message || (response.code === 0 ? '注册成功' : '注册失败')
            };
        } catch (error) {
            console.error('注册错误:', error);
            return { success: false, message: '注册失败：' + error.message };
        }
    }

    /**
     * 登出
     */
    logout() {
        this.userData = null;
        localStorage.removeItem('userData');
        localStorage.removeItem('authToken');
        this.notifyCallbacks();
    }

    /**
     * 检查登录状态
     */
    isLoggedIn() {
        return this.userData !== null;
    }

    /**
     * 获取当前用户信息
     */
    getUserData() {
        return this.userData;
    }

    /**
     * 监听用户状态变化
     */
    onChange(callback) {
        this.callbacks.push(callback);
    }

    /**
     * 通知所有监听器
     */
    notifyCallbacks() {
        this.callbacks.forEach(callback => callback(this.userData));
    }
}

// 创建全局用户管理器实例
const userManager = new UserManager();

// ==================== 数据格式化工具 ====================
const DataFormatter = {
    /**
     * 格式化日期
     */
    formatDate(date, format = 'YYYY-MM-DD') {
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const seconds = String(d.getSeconds()).padStart(2, '0');

        return format
            .replace('YYYY', year)
            .replace('MM', month)
            .replace('DD', day)
            .replace('HH', hours)
            .replace('mm', minutes)
            .replace('ss', seconds);
    },

    /**
     * 格式化数字（千分位）
     */
    formatNumber(num, decimals = 2) {
        if (num === null || num === undefined || isNaN(num)) return '--';
        return Number(num).toLocaleString('zh-CN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    },

    /**
     * 格式化百分比
     */
    formatPercent(num, decimals = 2) {
        if (num === null || num === undefined || isNaN(num)) return '--';
        return (num * 100).toFixed(decimals) + '%';
    },

    /**
     * 格式化货币
     */
    formatCurrency(num, symbol = '¥') {
        if (num === null || num === undefined || isNaN(num)) return '--';
        return symbol + this.formatNumber(num, 2);
    }
};

// ==================== 数据验证工具 ====================
const Validator = {
    /**
     * 验证邮箱
     */
    isEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    /**
     * 验证手机号
     */
    isPhone(phone) {
        const re = /^1[3-9]\d{9}$/;
        return re.test(phone);
    },

    /**
     * 验证密码强度
     */
    isStrongPassword(password) {
        // 至少8位，包含大小写字母和数字
        const re = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,}$/;
        return re.test(password);
    },

    /**
     * 验证用户名
     */
    isValidUsername(username) {
        // 3-20位字母、数字、下划线
        const re = /^[a-zA-Z0-9_]{3,20}$/;
        return re.test(username);
    },

    /**
     * 验证股票代码
     */
    isStockCode(code) {
        // 支持格式：000001.SZ 或 600000.SH
        const re = /^\d{6}\.(SZ|SH)$/;
        return re.test(code);
    }
};

// ==================== 本地存储封装 ====================
const Storage = {
    /**
     * 设置数据
     */
    set(key, value, expireMinutes = null) {
        const data = {
            value,
            expire: expireMinutes ? Date.now() + expireMinutes * 60000 : null
        };
        localStorage.setItem(key, JSON.stringify(data));
    },

    /**
     * 获取数据
     */
    get(key) {
        const data = localStorage.getItem(key);
        if (!data) return null;

        try {
            const parsed = JSON.parse(data);
            if (parsed.expire && Date.now() > parsed.expire) {
                this.remove(key);
                return null;
            }
            return parsed.value;
        } catch (e) {
            return data;
        }
    },

    /**
     * 删除数据
     */
    remove(key) {
        localStorage.removeItem(key);
    },

    /**
     * 清空所有数据
     */
    clear() {
        localStorage.clear();
    }
};

// ==================== 防抖和节流 ====================
const PerformanceUtils = {
    /**
     * 防抖函数
     */
    debounce(func, wait = 300) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * 节流函数
     */
    throttle(func, limit = 300) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

// ==================== 导出全局对象 ====================
window.ETF = {
    http,
    userManager,
    DataFormatter,
    Validator,
    Storage,
    PerformanceUtils,
    API_CONFIG
};

// 初始化用户管理器
userManager.init();
