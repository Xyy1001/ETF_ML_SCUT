/**
 * 模型训练页面交互脚本
 */

// 全局状态
const state = {
    models: [],
    dataFiles: [],
    isTraining: false,
    trainingId: null
};

// DOM元素
const elements = {
    modelList: document.getElementById('modelList'),
    dataList: document.getElementById('dataList'),
    dataSelect: document.getElementById('dataSelect'),
    refreshModels: document.getElementById('refreshModels'),
    refreshData: document.getElementById('refreshData'),
    startTrainBtn: document.getElementById('startTrainBtn'),
    stopTrainBtn: document.getElementById('stopTrainBtn'),
    progressPanel: document.getElementById('progressPanel'),
    logContent: document.getElementById('logContent'),
    clearLogBtn: document.getElementById('clearLogBtn'),
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toastMessage'),
    // 进度相关
    currentEpoch: document.getElementById('currentEpoch'),
    totalEpochs: document.getElementById('totalEpochs'),
    currentLoss: document.getElementById('currentLoss'),
    trainingProgress: document.getElementById('trainingProgress'),
    progressPercentage: document.getElementById('progressPercentage'),
    // 配置参数
    epochs: document.getElementById('epochs'),
    batchSize: document.getElementById('batchSize'),
    learningRate: document.getElementById('learningRate'),
    inputWindow: document.getElementById('inputWindow'),
    outputWindow: document.getElementById('outputWindow'),
    lstmHidden: document.getElementById('lstmHidden')
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    loadDataFiles();
    bindEvents();
});

/**
 * 加载已训练的模型列表
 */
async function loadModels() {
    try {
        const response = await fetch('/api/models');
        const data = await response.json();

        if (data.success) {
            state.models = data.data;
            renderModelList();
        } else {
            showToast('加载模型列表失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('加载模型列表失败:', error);
        showToast('网络错误，请检查服务器连接', 'error');
    }
}

/**
 * 渲染模型列表
 */
function renderModelList() {
    if (state.models.length === 0) {
        elements.modelList.innerHTML = `
            <div class="log-empty">暂无已训练的模型</div>
        `;
        return;
    }

    const html = state.models.map(model => `
        <div class="model-item">
            <div class="item-name">${model.name}</div>
            <div class="item-info">
                <span class="info-badge">📊 ${model.stock_code}</span>
                <span class="info-badge">💾 ${model.size}</span>
                <span class="info-badge">🕐 ${model.modified}</span>
            </div>
        </div>
    `).join('');

    elements.modelList.innerHTML = html;
}

/**
 * 加载可用训练数据列表
 */
async function loadDataFiles() {
    try {
        const response = await fetch('/api/training-data');
        const data = await response.json();

        if (data.success) {
            state.dataFiles = data.data;
            renderDataList();
            updateDataSelect();
        } else {
            showToast('加载数据列表失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('加载数据列表失败:', error);
        showToast('网络错误，请检查服务器连接', 'error');
    }
}

/**
 * 渲染数据列表
 */
function renderDataList() {
    if (state.dataFiles.length === 0) {
        elements.dataList.innerHTML = `
            <div class="log-empty">
                <p>暂无可用的训练数据</p>
                <p style="margin-top: 0.5rem; font-size: 0.85rem;">
                    请先在"数据处理"页面生成数据
                </p>
            </div>
        `;
        return;
    }

    const html = state.dataFiles.map(file => `
        <div class="data-item">
            <div class="item-name">${file.name}</div>
            <div class="item-info">
                <span class="info-badge">📈 ${file.stock_code}</span>
                <span class="info-badge">📏 ${file.rows} 行</span>
                <span class="info-badge">💾 ${file.size}</span>
                <span class="info-badge">🕐 ${file.modified}</span>
            </div>
        </div>
    `).join('');

    elements.dataList.innerHTML = html;
}

/**
 * 更新数据选择下拉框
 */
function updateDataSelect() {
    const options = state.dataFiles.map(file =>
        `<option value="${file.name}">${file.stock_code} (${file.rows}行)</option>`
    ).join('');

    elements.dataSelect.innerHTML = '<option value="">请选择训练数据...</option>' + options;
}

/**
 * 开始训练
 */
async function startTraining() {
    // 验证输入
    const dataFile = elements.dataSelect.value;
    if (!dataFile) {
        showToast('请选择训练数据文件', 'error');
        return;
    }

    const epochs = parseInt(elements.epochs.value);
    const batchSize = parseInt(elements.batchSize.value);
    const learningRate = parseFloat(elements.learningRate.value);
    const inputWindow = parseInt(elements.inputWindow.value);
    const outputWindow = parseInt(elements.outputWindow.value);
    const lstmHidden = parseInt(elements.lstmHidden.value);

    if (epochs < 1 || epochs > 1000) {
        showToast('训练轮数必须在1-1000之间', 'error');
        return;
    }

    if (batchSize < 1 || batchSize > 256) {
        showToast('批次大小必须在1-256之间', 'error');
        return;
    }

    // 更新UI状态
    state.isTraining = true;
    elements.startTrainBtn.style.display = 'none';
    elements.stopTrainBtn.style.display = 'flex';
    elements.progressPanel.style.display = 'block';

    // 重置进度
    elements.currentEpoch.textContent = '0';
    elements.totalEpochs.textContent = epochs;
    elements.currentLoss.textContent = '-';
    elements.trainingProgress.style.width = '0%';
    elements.progressPercentage.textContent = '0%';

    // 添加日志
    addLog(`开始训练 - 数据文件: ${dataFile}`);
    addLog(`配置: Epochs=${epochs}, Batch=${batchSize}, LR=${learningRate}`);
    addLog(`窗口: Input=${inputWindow}, Output=${outputWindow}, LSTM=${lstmHidden}`);

    try {
        const response = await fetch('/api/train', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                data_file: dataFile,
                epochs: epochs,
                batch_size: batchSize,
                learning_rate: learningRate,
                input_window: inputWindow,
                output_window: outputWindow,
                lstm_hidden: lstmHidden
            })
        });

        const data = await response.json();

        if (data.success) {
            state.trainingId = data.training_id;
            addLog(`训练任务已提交: ${data.training_id}`);
            showToast(data.message, 'success');

            // 模拟训练进度（实际应该通过WebSocket或轮询获取真实进度）
            simulateTraining(epochs);
        } else {
            addLog(`训练失败: ${data.message}`, 'error');
            showToast('训练失败: ' + data.message, 'error');
            stopTraining();
        }
    } catch (error) {
        console.error('训练请求失败:', error);
        addLog(`训练请求失败: ${error.message}`, 'error');
        showToast('网络错误，请检查服务器连接', 'error');
        stopTraining();
    }
}

/**
 * 模拟训练进度（实际应该从后端获取）
 */
function simulateTraining(totalEpochs) {
    let currentEpoch = 0;

    const interval = setInterval(() => {
        if (!state.isTraining) {
            clearInterval(interval);
            return;
        }

        currentEpoch++;
        const progress = (currentEpoch / totalEpochs) * 100;
        const loss = (Math.random() * 0.1 + 0.01).toFixed(6);

        // 更新进度
        elements.currentEpoch.textContent = currentEpoch;
        elements.currentLoss.textContent = loss;
        elements.trainingProgress.style.width = progress + '%';
        elements.progressPercentage.textContent = progress.toFixed(1) + '%';

        // 添加日志
        if (currentEpoch % 10 === 0 || currentEpoch === totalEpochs) {
            addLog(`Epoch ${currentEpoch}/${totalEpochs} - Loss: ${loss}`);
        }

        // 训练完成
        if (currentEpoch >= totalEpochs) {
            clearInterval(interval);
            addLog('训练完成！模型已保存');
            showToast('训练完成！', 'success');
            stopTraining();

            // 刷新模型列表
            setTimeout(() => {
                loadModels();
            }, 1000);
        }
    }, 1000); // 每秒更新一次（实际应该根据真实训练速度）
}

/**
 * 停止训练
 */
function stopTraining() {
    state.isTraining = false;
    state.trainingId = null;
    elements.startTrainBtn.style.display = 'flex';
    elements.stopTrainBtn.style.display = 'none';

    if (state.isTraining) {
        addLog('训练已停止');
        showToast('训练已停止', 'warning');
    }
}

/**
 * 添加日志
 */
function addLog(message, type = 'info') {
    // 如果是第一条日志，清空空状态提示
    if (elements.logContent.querySelector('.log-empty')) {
        elements.logContent.innerHTML = '';
    }

    const time = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    logEntry.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="log-message">${message}</span>
    `;

    elements.logContent.appendChild(logEntry);

    // 自动滚动到底部
    elements.logContent.scrollTop = elements.logContent.scrollHeight;
}

/**
 * 清空日志
 */
function clearLog() {
    elements.logContent.innerHTML = '<div class="log-empty">暂无训练日志</div>';
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
    // 刷新按钮
    elements.refreshModels.addEventListener('click', loadModels);
    elements.refreshData.addEventListener('click', loadDataFiles);

    // 训练控制按钮
    elements.startTrainBtn.addEventListener('click', startTraining);
    elements.stopTrainBtn.addEventListener('click', stopTraining);

    // 清空日志
    elements.clearLogBtn.addEventListener('click', clearLog);

    // 输入验证
    elements.epochs.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        if (value < 1) e.target.value = 1;
        if (value > 1000) e.target.value = 1000;
    });

    elements.batchSize.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        if (value < 1) e.target.value = 1;
        if (value > 256) e.target.value = 256;
    });
}

console.log('训练页面加载成功！');
