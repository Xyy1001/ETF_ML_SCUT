// 首页交互逻辑

document.addEventListener('DOMContentLoaded', function () {
    // 加载统计数据
    loadStatistics();

    // 平滑滚动
    setupSmoothScroll();

    // 导航栏激活状态
    setupNavigation();

    // 功能卡片点击跳转
    setupFeatureCards();
});

// 加载统计数据
async function loadStatistics() {
    try {
        // 加载数据统计
        const dataResponse = await fetch('/api/data/summary');
        const dataResult = await dataResponse.json();

        if (dataResult.success) {
            const stockCountEl = document.getElementById('stock-count');
            if (stockCountEl) {
                stockCountEl.textContent = dataResult.data.raw_count + '+';
            }
        }

        // 加载模型统计
        const modelResponse = await fetch('/api/models/summary');
        const modelResult = await modelResponse.json();

        if (modelResult.success) {
            const modelCountEl = document.getElementById('model-count');
            if (modelCountEl) {
                const totalModels = modelResult.data.lstm.model_count + (modelResult.data.gnn.model_exists ? 1 : 0);
                modelCountEl.textContent = totalModels;
            }
        }
    } catch (error) {
        console.error('加载统计数据失败:', error);
        document.getElementById('stock-count').textContent = '100+';
        document.getElementById('model-count').textContent = '20+';
    }
}

// 设置平滑滚动
function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// 设置导航栏
function setupNavigation() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link[href^="#"]');

    window.addEventListener('scroll', () => {
        let current = '';

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (pageYOffset >= sectionTop - 200) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === '#' + current) {
                link.classList.add('active');
            }
        });
    });
}

// 设置功能卡片点击事件
function setupFeatureCards() {
    const featureCards = document.querySelectorAll('.feature-card[data-page]');

    featureCards.forEach(card => {
        card.style.cursor = 'pointer';
        card.addEventListener('click', function () {
            const page = this.getAttribute('data-page');
            const urlMap = {
                'data_page': '/data',
                'models_page': '/models',
                'backtest_page': '/backtest',
                'ai_page': '/ai'
            };

            if (urlMap[page]) {
                window.location.href = urlMap[page];
            }
        });
    });
}
