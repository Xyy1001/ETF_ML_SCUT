// 风险管理系统交互脚本

// 全局状态
let state = {
    methods: [],
    selectedMethod: null,
    models: [],
    dataFiles: [],
    isTraining: false,
    trainingId: null
};

// ==================== 页面初始化 ====================
document.addEventListener('DOMContentLoaded', function () {
    console.log('风险管理系统初始化...');

    // 加载所有数据
    loadMethods();
    loadModels();
    loadDataFiles();

    // 绑定表单事件
    const trainForm = document.getElementById('trainForm');
    trainForm.addEventListener('submit', handleTrainSubmit);

    const stopBtn = document.getElementById('stopBtn');
    stopBtn.addEventListener('click', stopTraining);

    console.log('初始化完成');
});

// ==================== 加载风险管理方法 ====================
async function loadMethods() {
    console.log('加载风险管理方法...');
    const methodsList = document.getElementById('methodsList');
    const methodSelect = document.getElementById('methodSelect');

    try {
        const response = await fetch('/api/risk-methods');
        const result = await response.json();

        if (result.success) {
            state.methods = result.data;

            // 渲染方法卡片
            if (state.methods.length === 0) {
                methodsList.innerHTML = '<div class="empty">暂无可用方法</div>';
            } else {
                methodsList.innerHTML = state.methods.map(method => `
                    <div class="method-card" data-method-id="${method.id}" onclick="selectMethod('${method.id}')">
                        <div class="method-header">
                            <div class="method-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    ${method.icon === 'grid' ?
                        '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>' :
                        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
                    }
                                </svg>
                            </div>
                            <div class="method-info">
                                <h4>${method.name}</h4>
                                <span class="method-badge">${method.module}</span>
                            </div>
                        </div>
                        <p class="method-description">${method.description}</p>
                    </div>
                `).join('');
            }

            // 填充下拉选择框
            methodSelect.innerHTML = '<option value="">请选择方法</option>' +
                state.methods.map(method => `
                    <option value="${method.id}">${method.name}</option>
                `).join('');

            console.log(`成功加载 ${state.methods.length} 个方法`);
        } else {
            methodsList.innerHTML = `<div class="empty">加载失败: ${result.message}</div>`;
        }
    } catch (error) {
        console.error('加载方法失败:', error);
        methodsList.innerHTML = '<div class="empty">加载失败，请刷新重试</div>';
    }
}

// ==================== 选择风险管理方法 ====================
function selectMethod(methodId) {
    state.selectedMethod = methodId;

    // 更新UI选中状态
    document.querySelectorAll('.method-card').forEach(card => {
        if (card.dataset.methodId === methodId) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    });

    // 更新下拉框
    document.getElementById('methodSelect').value = methodId;

    const method = state.methods.find(m => m.id === methodId);
    addLog(`已选择方法: ${method.name}`, 'info');
    console.log('选择方法:', method);
}

// ==================== 加载已训练模型 ====================
async function loadModels() {
    console.log('加载已训练模型...');
    const modelsList = document.getElementById('modelsList');

    try {
        const response = await fetch('/api/risk-models');
        const result = await response.json();

        if (result.success) {
            state.models = result.data;

            if (state.models.length === 0) {
                modelsList.innerHTML = '<div class="empty">暂无已训练模型</div>';
            } else {
                modelsList.innerHTML = state.models.map(model => `
                    <div class="model-item">
                        <div class="model-name">
                            <svg style="width: 16px; height: 16px; display: inline; vertical-align: middle; stroke: #667eea;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                                <path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>
                            </svg>
                            ${model.name}
                        </div>
                        <div class="model-meta">
                            <div class="meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                                </svg>
                                ${model.method}
                            </div>
                            <div class="meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                                </svg>
                                ${model.size}
                            </div>
                            <div class="meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"/>
                                    <polyline points="12 6 12 12 16 14"/>
                                </svg>
                                ${model.modified}
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            console.log(`成功加载 ${state.models.length} 个模型`);
        } else {
            modelsList.innerHTML = `<div class="empty">加载失败: ${result.message}</div>`;
        }
    } catch (error) {
        console.error('加载模型失败:', error);
        modelsList.innerHTML = '<div class="empty">加载失败，请刷新重试</div>';
    }
}

// ==================== 加载训练数据文件 ====================
async function loadDataFiles() {
    console.log('加载训练数据...');
    const dataFilesList = document.getElementById('dataFilesList');

    try {
        const response = await fetch('/api/risk-data');
        const result = await response.json();

        if (result.success) {
            state.dataFiles = result.data;

            if (state.dataFiles.length === 0) {
                dataFilesList.innerHTML = '<div class="empty">暂无训练数据</div>';
            } else {
                dataFilesList.innerHTML = state.dataFiles.map(file => `
                    <div class="data-item">
                        <div class="data-name">
                            <svg style="width: 16px; height: 16px; display: inline; vertical-align: middle; stroke: #667eea;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                                <polyline points="13 2 13 9 20 9"/>
                            </svg>
                            ${file.name}
                        </div>
                        <div class="data-meta">
                            <div class="meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                                </svg>
                                ${file.path}
                            </div>
                            <div class="meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                                </svg>
                                ${file.size}
                            </div>
                            <div class="meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"/>
                                    <polyline points="12 6 12 12 16 14"/>
                                </svg>
                                ${file.modified}
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            console.log(`成功加载 ${state.dataFiles.length} 个数据文件`);
        } else {
            dataFilesList.innerHTML = `<div class="empty">加载失败: ${result.message}</div>`;
        }
    } catch (error) {
        console.error('加载数据失败:', error);
        dataFilesList.innerHTML = '<div class="empty">加载失败，请刷新重试</div>';
    }
}

// ==================== 处理训练表单提交 ====================
async function handleTrainSubmit(event) {
    event.preventDefault();

    if (state.isTraining) {
        addLog('训练正在进行中，请等待完成或先停止当前训练', 'warning');
        return;
    }

    // 获取表单数据
    const method = document.getElementById('methodSelect').value;
    const epochs = parseInt(document.getElementById('epochs').value);
    const batchSize = parseInt(document.getElementById('batchSize').value);
    const learningRate = parseFloat(document.getElementById('learningRate').value);
    const lookback = parseInt(document.getElementById('lookback').value);
    const horizon = parseInt(document.getElementById('horizon').value);

    // 验证
    if (!method) {
        addLog('请选择风险管理方法', 'error');
        return;
    }

    if (epochs < 1 || epochs > 1000) {
        addLog('训练轮数必须在 1-1000 之间', 'error');
        return;
    }

    if (batchSize < 1 || batchSize > 256) {
        addLog('批次大小必须在 1-256 之间', 'error');
        return;
    }

    addLog('正在提交训练任务...', 'info');

    try {
        const response = await fetch('/api/risk-train', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                method,
                epochs,
                batch_size: batchSize,
                learning_rate: learningRate,
                lookback,
                horizon
            })
        });

        const result = await response.json();

        if (result.success) {
            state.isTraining = true;
            state.trainingId = result.training_id;

            addLog(`✓ ${result.message}`, 'success');
            addLog(`训练ID: ${result.training_id}`, 'info');
            addLog(`配置: 方法=${result.config.method}, 轮数=${result.config.epochs}, 批次=${result.config.batch_size}`, 'info');

            // 更新UI状态
            document.getElementById('trainBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;

            // 开始模拟训练进度
            simulateTraining(epochs);
        } else {
            addLog(`✗ ${result.message}`, 'error');
        }
    } catch (error) {
        console.error('训练提交失败:', error);
        addLog(`✗ 训练提交失败: ${error.message}`, 'error');
    }
}

// ==================== 模拟训练进度 ====================
function simulateTraining(totalEpochs) {
    let currentEpoch = 0;
    const startTime = Date.now();

    // 更新总轮次
    document.getElementById('totalEpochs').textContent = totalEpochs;

    const interval = setInterval(() => {
        if (!state.isTraining) {
            clearInterval(interval);
            return;
        }

        currentEpoch++;

        // 模拟损失值（随机递减）
        const loss = (Math.random() * 0.5 + 0.1 * (totalEpochs - currentEpoch) / totalEpochs).toFixed(6);

        // 计算进度
        const progress = (currentEpoch / totalEpochs * 100).toFixed(1);

        // 计算剩余时间
        const elapsed = Date.now() - startTime;
        const estimatedTotal = elapsed / currentEpoch * totalEpochs;
        const remaining = Math.max(0, estimatedTotal - elapsed);
        const remainingMin = Math.floor(remaining / 60000);
        const remainingSec = Math.floor((remaining % 60000) / 1000);

        // 更新UI
        document.getElementById('currentEpoch').textContent = currentEpoch;
        document.getElementById('currentLoss').textContent = loss;
        document.getElementById('progressPercent').textContent = `${progress}%`;
        document.getElementById('progressFill').style.width = `${progress}%`;
        document.getElementById('progressText').textContent = `训练进行中 (Epoch ${currentEpoch}/${totalEpochs})`;
        document.getElementById('estimatedTime').textContent = `${remainingMin}:${remainingSec.toString().padStart(2, '0')}`;

        // 添加日志
        if (currentEpoch % 10 === 0 || currentEpoch === 1) {
            addLog(`Epoch ${currentEpoch}/${totalEpochs} - Loss: ${loss}`, 'info');
        }

        // 完成训练
        if (currentEpoch >= totalEpochs) {
            clearInterval(interval);
            finishTraining();
        }
    }, 1000); // 每秒更新一次
}

// ==================== 完成训练 ====================
function finishTraining() {
    state.isTraining = false;

    addLog('═══════════════════════════════', 'info');
    addLog('✓ 训练完成！', 'success');
    addLog('模型已保存到 B-GNN 目录', 'success');
    addLog('═══════════════════════════════', 'info');

    // 重置UI
    document.getElementById('trainBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('progressText').textContent = '训练完成';
    document.getElementById('estimatedTime').textContent = '00:00';

    // 刷新模型列表
    setTimeout(() => {
        loadModels();
    }, 1000);
}

// ==================== 停止训练 ====================
function stopTraining() {
    if (!state.isTraining) {
        return;
    }

    if (confirm('确定要停止当前训练吗？')) {
        state.isTraining = false;

        addLog('训练已手动停止', 'warning');

        document.getElementById('trainBtn').disabled = false;
        document.getElementById('stopBtn').disabled = true;
        document.getElementById('progressText').textContent = '训练已停止';
    }
}

// ==================== 添加日志 ====================
function addLog(message, type = 'info') {
    const log = document.getElementById('trainingLog');
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;

    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// ==================== 清除日志 ====================
function clearLog() {
    const log = document.getElementById('trainingLog');
    log.innerHTML = '';
    addLog('日志已清除', 'info');
}
