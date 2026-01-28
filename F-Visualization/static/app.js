/**
 * 股票数据处理系统 - 前端交互脚本
 */

// 全局状态
const state = {
    stocks: [],
    selectedStocks: new Set(),
    filteredStocks: []
};

// DOM元素
const elements = {
    searchInput: document.getElementById('searchInput'),
    stockList: document.getElementById('stockList'),
    selectedTags: document.getElementById('selectedTags'),
    selectedCount: document.getElementById('selectedCount'),
    clearBtn: document.getElementById('clearBtn'),
    startDate: document.getElementById('startDate'),
    endDate: document.getElementById('endDate'),
    atrPeriod: document.getElementById('atrPeriod'),
    rsiPeriod: document.getElementById('rsiPeriod'),
    processBtn: document.getElementById('processBtn'),
    progressContainer: document.getElementById('progressContainer'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    resultContainer: document.getElementById('resultContainer'),
    resultMessage: document.getElementById('resultMessage'),
    resultFiles: document.getElementById('resultFiles'),
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toastMessage')
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initializeDates();
    loadStocks();
    bindEvents();
});

/**
 * 初始化日期
 */
function initializeDates() {
    const today = new Date();
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(today.getFullYear() - 1);

    elements.endDate.value = formatDate(today);
    elements.startDate.value = formatDate(oneYearAgo);
}

/**
 * 格式化日期
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * 加载股票列表
 */
async function loadStocks() {
    try {
        const response = await fetch('/api/stocks');
        const data = await response.json();

        if (data.success) {
            state.stocks = data.data;
            state.filteredStocks = data.data;
            renderStockList();
        } else {
            showToast('加载股票列表失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('加载股票列表失败:', error);
        showToast('网络错误，请检查服务器连接', 'error');
    }
}

/**
 * 渲染股票列表
 */
function renderStockList() {
    if (state.filteredStocks.length === 0) {
        elements.stockList.innerHTML = `
            <div class="loading">
                <p>未找到匹配的股票</p>
            </div>
        `;
        return;
    }

    const html = state.filteredStocks.map(stock => `
        <div class="stock-item ${state.selectedStocks.has(stock.ts_code) ? 'selected' : ''}" 
             data-code="${stock.ts_code}" 
             onclick="toggleStock('${stock.ts_code}')">
            <div class="stock-code">${stock.ts_code}</div>
            <div class="stock-info">
                <span>${stock.name}</span>
                <span>${stock.industry || '未分类'}</span>
            </div>
        </div>
    `).join('');

    elements.stockList.innerHTML = html;
}

/**
 * 切换股票选择
 */
function toggleStock(code) {
    if (state.selectedStocks.has(code)) {
        state.selectedStocks.delete(code);
    } else {
        state.selectedStocks.add(code);
    }

    updateSelectedStocks();
    renderStockList();
}

/**
 * 更新已选股票显示
 */
function updateSelectedStocks() {
    elements.selectedCount.textContent = state.selectedStocks.size;

    if (state.selectedStocks.size === 0) {
        elements.selectedTags.innerHTML = '<p style="color: var(--text-muted); text-align: center;">尚未选择股票</p>';
        return;
    }

    const tags = Array.from(state.selectedStocks).map(code => {
        const stock = state.stocks.find(s => s.ts_code === code);
        return `
            <div class="stock-tag">
                <span>${stock ? stock.name : code}</span>
                <button class="tag-remove" onclick="removeStock('${code}')">&times;</button>
            </div>
        `;
    }).join('');

    elements.selectedTags.innerHTML = tags;
}

/**
 * 移除股票
 */
function removeStock(code) {
    state.selectedStocks.delete(code);
    updateSelectedStocks();
    renderStockList();
}

/**
 * 清空选择
 */
function clearSelection() {
    state.selectedStocks.clear();
    updateSelectedStocks();
    renderStockList();
}

/**
 * 搜索股票
 */
function searchStocks(query) {
    const lowerQuery = query.toLowerCase().trim();

    if (!lowerQuery) {
        state.filteredStocks = state.stocks;
    } else {
        state.filteredStocks = state.stocks.filter(stock =>
            stock.ts_code.toLowerCase().includes(lowerQuery) ||
            stock.name.toLowerCase().includes(lowerQuery) ||
            (stock.industry && stock.industry.toLowerCase().includes(lowerQuery)) ||
            (stock.area && stock.area.toLowerCase().includes(lowerQuery))
        );
    }

    renderStockList();
}

/**
 * 处理数据
 */
async function processData() {
    // 验证输入
    if (state.selectedStocks.size === 0) {
        showToast('请至少选择一只股票', 'error');
        return;
    }

    const startDate = elements.startDate.value;
    const endDate = elements.endDate.value;

    if (!startDate || !endDate) {
        showToast('请选择开始和结束日期', 'error');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        showToast('开始日期不能晚于结束日期', 'error');
        return;
    }

    const atrPeriod = parseInt(elements.atrPeriod.value);
    const rsiPeriod = parseInt(elements.rsiPeriod.value);

    if (atrPeriod < 1 || atrPeriod > 100) {
        showToast('ATR周期必须在1-100之间', 'error');
        return;
    }

    if (rsiPeriod < 1 || rsiPeriod > 100) {
        showToast('RSI周期必须在1-100之间', 'error');
        return;
    }

    // 显示进度
    elements.processBtn.disabled = true;
    elements.resultContainer.style.display = 'none';
    elements.progressContainer.style.display = 'block';
    elements.progressFill.style.width = '50%';
    elements.progressText.textContent = '正在处理数据...';

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_codes: Array.from(state.selectedStocks),
                start_date: startDate,
                end_date: endDate,
                atr_period: atrPeriod,
                rsi_period: rsiPeriod
            })
        });

        const data = await response.json();

        if (data.success) {
            // 完成进度
            elements.progressFill.style.width = '100%';
            elements.progressText.textContent = '处理完成！';

            setTimeout(() => {
                elements.progressContainer.style.display = 'none';
                showResult(data);
            }, 500);

            showToast(data.message, 'success');
        } else {
            elements.progressContainer.style.display = 'none';
            showToast('处理失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('处理数据失败:', error);
        elements.progressContainer.style.display = 'none';
        showToast('网络错误，请检查服务器连接', 'error');
    } finally {
        elements.processBtn.disabled = false;
        elements.progressFill.style.width = '0%';
    }
}

/**
 * 显示结果
 */
function showResult(data) {
    elements.resultMessage.textContent = data.message;

    const filesHtml = data.files.map(file => `
        <div class="file-item">📄 ${file}</div>
    `).join('');

    elements.resultFiles.innerHTML = `
        <div style="margin-bottom: 8px; color: var(--text-secondary);">
            保存路径: ${data.save_path}
        </div>
        ${filesHtml}
    `;

    elements.resultContainer.style.display = 'block';
}

/**
 * 显示Toast通知
 */
function showToast(message, type = 'info') {
    elements.toastMessage.textContent = message;
    elements.toast.className = 'toast show ' + type;

    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

/**
 * 绑定事件
 */
function bindEvents() {
    // 搜索
    elements.searchInput.addEventListener('input', (e) => {
        searchStocks(e.target.value);
    });

    // 清空选择
    elements.clearBtn.addEventListener('click', clearSelection);

    // 处理按钮
    elements.processBtn.addEventListener('click', processData);

    // 输入验证
    elements.atrPeriod.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        if (value < 1) e.target.value = 1;
        if (value > 100) e.target.value = 100;
    });

    elements.rsiPeriod.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        if (value < 1) e.target.value = 1;
        if (value > 100) e.target.value = 100;
    });
}
