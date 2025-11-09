// web/static/js/auth.js
import { connectWebSocket } from './auth-websocket.js';

// DOM Elements
const authModal = document.getElementById('auth-modal');
const authTitle = document.getElementById('auth-title');
const authSubtitle = document.getElementById('auth-subtitle');
const authError = document.getElementById('auth-error'); 

const usernameInputGroup = document.getElementById('username-input-group');
const passwordInputGroup = document.getElementById('password-input-group');
const emailInputGroup = document.getElementById('email-input-group');
const tokenInputGroup = document.getElementById('token-input-group');

const authUsernameInput = document.getElementById('auth-username');
const authPasswordInput = document.getElementById('auth-password');
const authEmailInput = document.getElementById('auth-email');
const authTokenInput = document.getElementById('auth-token');

const mainAuthBtn = document.getElementById('main-auth-btn');
const authSwitchText = document.getElementById('auth-switch-text');
const secondarySwitchText = document.getElementById('secondary-switch-text');

let authMode = 'login'; 

function setAuthMode(newMode) {
    authMode = newMode;
    hideAuthError();
    hideAuthSuccessMessage();

    usernameInputGroup.style.display = 'none';
    passwordInputGroup.style.display = 'none';
    emailInputGroup.style.display = 'none';
    tokenInputGroup.style.display = 'none';

    switch (authMode) {
        case 'login':
            authTitle.textContent = '欢迎回来';
            authSubtitle.textContent = '请登录以继续';
            usernameInputGroup.style.display = 'block';
            passwordInputGroup.style.display = 'block';
            mainAuthBtn.textContent = '登录';
            authSwitchText.innerHTML = '没有账户？ <a href="#" id="auth-switch-link" class="modal__switch-link">立即注册</a>';
            secondarySwitchText.innerHTML = '收到了验证码？ <a href="#" id="secondary-switch-link" class="modal__switch-link">验证邮箱</a>';
            secondarySwitchText.style.display = 'block';
            break;
        case 'register':
            authTitle.textContent = '创建账户';
            authSubtitle.textContent = '欢迎加入SimpleChannel';
            usernameInputGroup.style.display = 'block';
            passwordInputGroup.style.display = 'block';
            emailInputGroup.style.display = 'block';
            mainAuthBtn.textContent = '注册';
            authSwitchText.innerHTML = '已有账户？ <a href="#" id="auth-switch-link" class="modal__switch-link">立即登录</a>';
            secondarySwitchText.style.display = 'none';
            break;
        case 'verify':
            authTitle.textContent = '验证您的邮箱';
            authSubtitle.textContent = '请输入邮件中的用户名和验证令牌';
            usernameInputGroup.style.display = 'block';
            tokenInputGroup.style.display = 'block';
            mainAuthBtn.textContent = '提交验证';
            authSwitchText.innerHTML = '返回 <a href="#" id="auth-switch-link" class="modal__switch-link">登录</a>';
            secondarySwitchText.style.display = 'none';
            break;
    }
    bindSwitchLinks();
}

function bindSwitchLinks() {
    const oldAuthSwitchLink = document.getElementById('auth-switch-link');
    if (oldAuthSwitchLink) {
        oldAuthSwitchLink.replaceWith(oldAuthSwitchLink.cloneNode(true));
    }
    const oldSecondarySwitchLink = document.getElementById('secondary-switch-link');
    if (oldSecondarySwitchLink) {
        oldSecondarySwitchLink.replaceWith(oldSecondarySwitchLink.cloneNode(true));
    }

    const authSwitchLink = document.getElementById('auth-switch-link');
    const secondarySwitchLink = document.getElementById('secondary-switch-link');

    if (authSwitchLink) {
        authSwitchLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (authMode === 'register' || authMode === 'verify') {
                setAuthMode('login');
            } else {
                setAuthMode('register');
            }
        });
    }


    if (secondarySwitchLink && secondarySwitchText.style.display !== 'none') {
        secondarySwitchLink.addEventListener('click', (e) => {
            e.preventDefault();
            setAuthMode('verify');
        });
    }
}

export function initializeAuth() {
    mainAuthBtn.addEventListener('click', () => {
        const username = authUsernameInput.value.trim();

        if (authMode === 'login') {
            const password = authPasswordInput.value.trim();
            if (username && password) {
                setAuthFormState(true);
                connectWebSocket({ action: "login", username, password });
            } else {
                showAuthError('请输入用户名和密码。');
            }
        } else if (authMode === 'register') {
            const password = authPasswordInput.value.trim();
            const email = authEmailInput.value.trim();
            if (username && password && email) {
                setAuthFormState(true);
                connectWebSocket({ action: "register", username, password, email });
            } else {
                showAuthError('请输入用户名、密码和邮箱。');
            }
        } else if (authMode === 'verify') {
            const token = authTokenInput.value.trim();
            if (username && token) {
                setAuthFormState(true);
                connectWebSocket({ action: "verify", username, token });
            } else {
                showAuthError('请输入用户名和验证令牌。');
            }
        }
    });
    setAuthMode('login');
}

function setAuthFormState(isLoading) {
    mainAuthBtn.disabled = isLoading;
    authUsernameInput.disabled = isLoading;
    authPasswordInput.disabled = isLoading;
    authEmailInput.disabled = isLoading;
    authTokenInput.disabled = isLoading;

    if (isLoading) {
        if(authMode === 'login') mainAuthBtn.textContent = "登录中...";
        else if(authMode === 'register') mainAuthBtn.textContent = "注册中...";
        else mainAuthBtn.textContent = "验证中...";
    } else {
        if(authMode === 'login') mainAuthBtn.textContent = "登录";
        else if(authMode === 'register') mainAuthBtn.textContent = "注册";
        else mainAuthBtn.textContent = "提交验证";
    }
}

let authSuccessMessageElement = null;

function getAuthSuccessMessageElement() {
    if (!authSuccessMessageElement) {
        authSuccessMessageElement = document.createElement('div');
        authSuccessMessageElement.classList.add('modal__success-message');
        authSuccessMessageElement.style.display = 'none';
        authError.parentNode.insertBefore(authSuccessMessageElement, authError.nextSibling);
    }
    return authSuccessMessageElement;
}

function showAuthError(message) {
    hideAuthSuccessMessage();
    authError.textContent = message;
    authError.style.display = 'block';
}

function hideAuthError() {
    authError.style.display = 'none';
}

export function showAuthSuccessMessageInModal(message) {
    setAuthFormState(false);
    hideAuthError();
    const successEl = getAuthSuccessMessageElement();
    successEl.textContent = message;
    successEl.style.display = 'block';
    
    if (authMode === 'verify' || authMode === 'register') {
        setAuthMode('login');
    }
}

function hideAuthSuccessMessage() {
    if (authSuccessMessageElement) {
        authSuccessMessageElement.style.display = 'none';
    }
}

export function switchToVerifyMode() {
    setAuthMode('verify');
}

export function showAuthSystemMessageInModal(message, isSuccess = false) {
    if (isSuccess) {
        showAuthSuccessMessageInModal(message);
    } else {
        setAuthFormState(false);
        showAuthError(message);
    }
}

export function dispatchAuthSuccess(token) {
    const event = new CustomEvent('authSuccess', { detail: { token } });
    document.dispatchEvent(event);
}

// 修复 Bug 2: 导出 showGlobalAuthError 函数
export function showGlobalAuthError(message) {
    setAuthFormState(false);
    showAuthError(message);
}