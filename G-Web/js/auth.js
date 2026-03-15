(function () {
    function showInlineAlert(alertBox, message, type = 'error') {
        if (!alertBox) return;
        alertBox.textContent = message;
        alertBox.className = `alert alert-${type} active`;
        setTimeout(() => {
            alertBox.classList.remove('active');
        }, 5000);
    }

    function initLoginPage() {
        const loginForm = document.getElementById('loginForm');
        if (!loginForm || !window.ETF) return;

        const submitBtn = document.getElementById('submitBtn');
        const alertBox = document.getElementById('alertBox');
        const validator = new ETF.FormValidator(loginForm);

        const remembered = ETF.Storage.get('rememberedUsername');
        if (remembered) {
            const usernameEl = document.getElementById('username');
            const rememberEl = document.getElementById('rememberMe');
            if (usernameEl) usernameEl.value = remembered;
            if (rememberEl) rememberEl.checked = true;
        }

        if (ETF.userManager.isLoggedIn()) {
            const redirect = new URLSearchParams(window.location.search).get('redirect') || 'index.html';
            window.location.href = redirect;
            return;
        }

        loginForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            const rememberMe = document.getElementById('rememberMe').checked;

            const isValid = validator.validate({
                username: [
                    { required: true, message: '请输入用户名' },
                    { validator: ETF.Validator.isValidUsername, message: '用户名格式不正确（3-20位字母、数字、下划线）' }
                ],
                password: [
                    { required: true, message: '请输入密码' },
                    { minLength: 6, message: '密码至少6位' }
                ]
            });

            if (!isValid) {
                ETF.Toast.error('请检查输入信息');
                return;
            }

            ETF.Loading.show('正在登录...');
            submitBtn.disabled = true;
            submitBtn.textContent = '登录中...';

            try {
                const result = await ETF.userManager.login(username, password);

                if (result.success) {
                    if (rememberMe) {
                        ETF.Storage.set('rememberedUsername', username, 60 * 24 * 30);
                    } else {
                        ETF.Storage.remove('rememberedUsername');
                    }

                    ETF.Toast.success('登录成功！即将跳转...');
                    setTimeout(() => {
                        const redirect = new URLSearchParams(window.location.search).get('redirect') || 'index.html';
                        window.location.href = redirect;
                    }, 800);
                    return;
                }

                showInlineAlert(alertBox, result.message || '登录失败，请检查用户名和密码', 'error');
            } catch (error) {
                console.error('登录错误:', error);
                showInlineAlert(alertBox, '网络错误，请检查 API 服务是否启动', 'error');
            } finally {
                ETF.Loading.hide();
                submitBtn.disabled = false;
                submitBtn.textContent = '登录';
            }
        });

        document.getElementById('password').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                loginForm.dispatchEvent(new Event('submit'));
            }
        });

        window.showAlert = function (message, type = 'error') {
            showInlineAlert(alertBox, message, type);
        };
    }

    function initRegisterPage() {
        const registerForm = document.getElementById('registerForm');
        if (!registerForm || !window.ETF) return;

        const submitBtn = document.getElementById('submitBtn');
        const alertBox = document.getElementById('alertBox');
        const passwordInput = document.getElementById('password');
        const passwordStrength = document.getElementById('passwordStrength');
        const passwordStrengthBar = document.getElementById('passwordStrengthBar');
        const validator = new ETF.FormValidator(registerForm);

        passwordInput.addEventListener('input', function () {
            const password = this.value;
            if (!password) {
                passwordStrength.classList.remove('active');
                return;
            }

            passwordStrength.classList.add('active');

            let strength = 0;
            if (password.length >= 6) strength++;
            if (password.length >= 8) strength++;
            if (/[a-z]/.test(password)) strength++;
            if (/[A-Z]/.test(password)) strength++;
            if (/[0-9]/.test(password)) strength++;
            if (/[^a-zA-Z0-9]/.test(password)) strength++;

            passwordStrengthBar.className = 'password-strength-bar';
            if (strength <= 2) {
                passwordStrengthBar.classList.add('strength-weak');
            } else if (strength <= 4) {
                passwordStrengthBar.classList.add('strength-medium');
            } else {
                passwordStrengthBar.classList.add('strength-strong');
            }
        });

        registerForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;

            const isValid = validator.validate({
                username: [
                    { required: true, message: '请输入用户名' },
                    { pattern: /^[a-zA-Z0-9_]{4,20}$/, message: '用户名格式无效（4-20字符，只能包含字母、数字、下划线）' }
                ],
                password: [
                    { required: true, message: '请输入密码' },
                    { minLength: 6, message: '密码至少6位' }
                ],
                email: [
                    { validator: (value) => !value || ETF.Validator.isEmail(value), message: '邮箱格式无效' }
                ],
                phone: [
                    { validator: (value) => !value || ETF.Validator.isPhone(value), message: '手机号格式无效' }
                ]
            });

            if (!isValid) {
                ETF.Toast.error('请检查输入信息');
                return;
            }

            if (password !== confirmPassword) {
                showInlineAlert(alertBox, '两次输入的密码不一致', 'error');
                return;
            }

            const formData = {
                username: document.getElementById('username').value.trim(),
                password,
                email: document.getElementById('email').value.trim(),
                phone: document.getElementById('phone').value.trim(),
                real_name: document.getElementById('realName').value.trim()
            };

            Object.keys(formData).forEach((key) => {
                if (!formData[key]) {
                    delete formData[key];
                }
            });

            submitBtn.disabled = true;
            submitBtn.textContent = '注册中...';
            ETF.Loading.show('正在注册...');

            try {
                const result = await ETF.userManager.register(formData);
                if (result.success) {
                    showInlineAlert(alertBox, '注册成功！即将跳转到登录页面...', 'success');
                    setTimeout(() => {
                        window.location.href = 'login.html';
                    }, 900);
                    return;
                }

                showInlineAlert(alertBox, result.message || '注册失败，请稍后重试', 'error');
            } catch (error) {
                console.error('注册错误:', error);
                showInlineAlert(alertBox, '网络错误，请检查 API 服务是否启动', 'error');
            } finally {
                ETF.Loading.hide();
                submitBtn.disabled = false;
                submitBtn.textContent = '立即注册';
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initLoginPage();
        initRegisterPage();
    });
})();
