// web/static/js/login.js
// 这个文件专门负责登录/注册/验证页面的逻辑
import { initializeAuth } from './auth.js';
import * as ui from './ui.js';

// 初始化认证模态框的事件绑定
document.addEventListener('DOMContentLoaded', () => {
    initializeAuth();

    // 添加: 登录成功后重定向
    // 我们通过监听一个自定义事件来实现
    document.addEventListener('authSuccess', (event) => {
        const { token } = event.detail;
        if (token) {
            // 将 token 存入 cookie，以便后端路由可以识别
            document.cookie = `session_token=${token};path=/;max-age=86400`; // 有效期1天
            // 重定向到主应用页面
            ui.showNotificationBar("登录成功，正在跳转...", false);
            setTimeout(() => {
                window.location.href = '/app';
            }, 500);
        }
    });
});