// 数据展示页面交互

let currentStock = null;
let stockData = null;

document.addEventListener('DOMContentLoaded', function () {
    loadDataSummary();
    setupTabs();
    setupSearch();
});

// 加载数据概览
async function loadDataSummary() {
    try {
        const response = await fetch('/api/data/summary');
        const result = await response.json();

        if (result.success) {
            document.getElementById('raw-stock-count').textContent = result.data.raw_count;
            document.getElementById('indicator-stock-count').textContent = result.data.indicator_count;
            document.getElementById('raw-file-count').textContent = result.data.raw_files;
            document.getElementById('indicator-file-count').textContent = result.data.indicator_files;

            renderStockList(result.data.stock_list);
        }
    } catch (error) {
        console.error('加载数据概览失败:', error);
        showError('加载数据失败，请刷新重试');
    }
}

// 渲染股票列表
function renderStockList(stocks) {
    const listEl = document.getElementById('stock-list');

    if (!stocks || stocks.length === 0) {
        listEl.innerHTML = '<div class="loading-placeholder">暂无数据</div>';
        return;
    }

    listEl.innerHTML = '';
    stocks.forEach(stock => {
        const item = document.createElement('div');
        item.className = 'stock-item';
        item.innerHTML = `<div class="stock-code">${stock}</div>`;
        item.onclick = () => selectStock(stock, item);
        listEl.appendChild(item);
    });
}

// 选择股票
async function selectStock(stockCode, element) {
    // 更新选中状态
    document.querySelectorAll('.stock-item').forEach(item => {
        item.classList.remove('active');
    });
    element.classList.add('active');

    currentStock = stockCode;

    // 加载股票数据
    try {
        const response = await fetch(`/api/data/stock/${stockCode}`);
        const result = await response.json();

        if (result.success) {
            stockData = result.data;
            renderData();
        }
    } catch (error) {
        console.error('加载股票数据失败:', error);
        showError('加载股票数据失败');
    }
}

// 渲染数据
function renderData() {
    if (!stockData) return;

    const activeTab = document.querySelector('.tab-btn.active').dataset.tab;

    if (activeTab === 'raw') {
        renderRawData();
    } else {
        renderIndicatorData();
    }
}

// 渲染原始数据
function renderRawData() {
    const infoEl = document.getElementById('raw-data-info');
    const wrapperEl = document.getElementById('raw-table-wrapper');
    const titleEl = document.getElementById('raw-table-title');
    const tableEl = document.getElementById('raw-data-table');

    if (!stockData.raw_data || stockData.raw_data.length === 0) {
        infoEl.style.display = 'block';
        infoEl.innerHTML = '<p class="info-text">该股票暂无原始数据</p>';
        wrapperEl.style.display = 'none';
        return;
    }

    infoEl.style.display = 'none';
    wrapperEl.style.display = 'block';
    titleEl.textContent = `${currentStock} - 原始数据`;

    // 生成表格
    const data = stockData.raw_data;
    const columns = Object.keys(data[0]);

    let tableHTML = '<thead><tr>';
    columns.forEach(col => {
        tableHTML += `<th>${col}</th>`;
    });
    tableHTML += '</tr></thead><tbody>';

    data.forEach(row => {
        tableHTML += '<tr>';
        columns.forEach(col => {
            const value = row[col];
            const formatted = typeof value === 'number' ? value.toFixed(2) : value;
            tableHTML += `<td>${formatted}</td>`;
        });
        tableHTML += '</tr>';
    });

    tableHTML += '</tbody>';
    tableEl.innerHTML = tableHTML;
}

// 渲染技术指标数据
function renderIndicatorData() {
    const infoEl = document.getElementById('indicator-data-info');
    const wrapperEl = document.getElementById('indicator-table-wrapper');
    const titleEl = document.getElementById('indicator-table-title');
    const tableEl = document.getElementById('indicator-data-table');

    if (!stockData.indicator_data || stockData.indicator_data.length === 0) {
        infoEl.style.display = 'block';
        infoEl.innerHTML = '<p class="info-text">该股票暂无技术指标数据</p>';
        wrapperEl.style.display = 'none';
        return;
    }

    infoEl.style.display = 'none';
    wrapperEl.style.display = 'block';
    titleEl.textContent = `${currentStock} - 技术指标数据`;

    // 生成表格
    const data = stockData.indicator_data;
    const columns = Object.keys(data[0]);

    let tableHTML = '<thead><tr>';
    columns.forEach(col => {
        tableHTML += `<th>${col}</th>`;
    });
    tableHTML += '</tr></thead><tbody>';

    data.forEach(row => {
        tableHTML += '<tr>';
        columns.forEach(col => {
            const value = row[col];
            const formatted = typeof value === 'number' ? value.toFixed(4) : value;
            tableHTML += `<td>${formatted}</td>`;
        });
        tableHTML += '</tr>';
    });

    tableHTML += '</tbody>';
    tableEl.innerHTML = tableHTML;
}

// 设置标签页
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;

            // 更新按钮状态
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // 更新内容显示
            tabContents.forEach(content => {
                content.classList.remove('active');
            });

            if (targetTab === 'raw') {
                document.getElementById('raw-data-tab').classList.add('active');
            } else {
                document.getElementById('indicator-data-tab').classList.add('active');
            }

            // 重新渲染数据
            if (stockData) {
                renderData();
            }
        });
    });
}

// 设置搜索
function setupSearch() {
    const searchInput = document.getElementById('stock-search');

    searchInput.addEventListener('input', (e) => {
        const keyword = e.target.value.toLowerCase();
        const items = document.querySelectorAll('.stock-item');

        items.forEach(item => {
            const code = item.querySelector('.stock-code').textContent.toLowerCase();
            if (code.includes(keyword)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    });
}

// 下载数据
function downloadData(type) {
    if (!stockData || !currentStock) {
        alert('请先选择股票');
        return;
    }

    const data = type === 'raw' ? stockData.raw_data : stockData.indicator_data;

    if (!data || data.length === 0) {
        alert('暂无数据可下载');
        return;
    }

    // 转换为CSV
    const columns = Object.keys(data[0]);
    let csv = columns.join(',') + '\n';

    data.forEach(row => {
        const values = columns.map(col => row[col]);
        csv += values.join(',') + '\n';
    });

    // 下载
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${currentStock}_${type}_data.csv`;
    link.click();
}

// 显示错误
function showError(message) {
    alert(message);
}
