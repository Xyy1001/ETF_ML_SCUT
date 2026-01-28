/**
 * 首页交互脚本
 */

// 平滑滚动
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

// 导航栏激活状态
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-link');

function updateActiveNav() {
    const scrollY = window.pageYOffset;

    sections.forEach(section => {
        const sectionHeight = section.offsetHeight;
        const sectionTop = section.offsetTop - 100;
        const sectionId = section.getAttribute('id');

        if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === `#${sectionId}`) {
                    link.classList.add('active');
                }
            });
        }
    });
}

// 监听滚动事件
window.addEventListener('scroll', updateActiveNav);

// 导航栏背景透明度
const navbar = document.querySelector('.navbar');
window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
        navbar.style.background = 'rgba(15, 15, 30, 0.98)';
    } else {
        navbar.style.background = 'rgba(15, 15, 30, 0.95)';
    }
});

// 统计数字动画
function animateValue(element, start, end, duration) {
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            current = end;
            clearInterval(timer);
        }

        if (element.textContent.includes('+')) {
            element.textContent = Math.floor(current) + '+';
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// 观察器，用于触发动画
const observerOptions = {
    threshold: 0.5,
    rootMargin: '0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            // 卡片渐入动画
            if (entry.target.classList.contains('feature-card') ||
                entry.target.classList.contains('team-card') ||
                entry.target.classList.contains('tech-feature')) {
                entry.target.style.opacity = '0';
                entry.target.style.transform = 'translateY(30px)';

                setTimeout(() => {
                    entry.target.style.transition = 'all 0.6s ease';
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, 100);

                observer.unobserve(entry.target);
            }

            // 统计数字动画
            if (entry.target.classList.contains('hero-stats')) {
                const statNumbers = entry.target.querySelectorAll('.stat-number');
                statNumbers.forEach((stat, index) => {
                    const text = stat.textContent;
                    if (text.includes('+')) {
                        const value = parseInt(text.replace('+', ''));
                        animateValue(stat, 0, value, 2000);
                    } else if (text === '实时') {
                        // 实时文字不需要动画
                    } else {
                        const value = parseInt(text);
                        animateValue(stat, 0, value, 2000);
                    }
                });
                observer.unobserve(entry.target);
            }
        }
    });
}, observerOptions);

// 观察所有需要动画的元素
document.addEventListener('DOMContentLoaded', () => {
    const animatedElements = document.querySelectorAll('.feature-card, .team-card, .tech-feature, .hero-stats');
    animatedElements.forEach(el => observer.observe(el));
});

// 移动端菜单切换（如需要）
const createMobileMenu = () => {
    const navMenu = document.querySelector('.nav-menu');
    const menuToggle = document.createElement('button');
    menuToggle.className = 'menu-toggle';
    menuToggle.innerHTML = '☰';
    menuToggle.style.cssText = `
        display: none;
        background: none;
        border: none;
        color: var(--text-primary);
        font-size: 1.5rem;
        cursor: pointer;
    `;

    if (window.innerWidth <= 768) {
        document.querySelector('.nav-container').insertBefore(menuToggle, navMenu);
        menuToggle.style.display = 'block';

        menuToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
        });
    }
};

// 响应式处理
window.addEventListener('resize', () => {
    if (window.innerWidth <= 768) {
        createMobileMenu();
    }
});

// 页面加载完成后的处理
window.addEventListener('load', () => {
    // 移除加载动画（如果有）
    document.body.classList.add('loaded');
});

console.log('ETF-ML 首页加载成功！');
