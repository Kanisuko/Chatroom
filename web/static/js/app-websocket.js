// web/static/js/app-websocket.js
import { getStore } from './state.js';
import * as ui from './ui.js';

let socket;
let heartbeatInterval = null;
const MAX_RECONNECT_ATTEMPTS = 5;

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

export function getAuthHeader() {
    const token = getCookie('session_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

export function connectAppWebSocket(callbacks) {
    const { onOpen, onMessage, onClose, onError } = callbacks;

    if (socket && socket.readyState !== WebSocket.CLOSED) {
        socket.close();
    }
    
    // 修改: 从 window.location 获取主机和端口，而不是 data-* 属性
    const wsProtocol = document.body.dataset.wsProtocol;
    const wsHost = window.location.hostname;
    const wsPort = window.location.port;
    const token = getCookie('session_token');

    if (!token) {
        console.error("未找到会话令牌，无法连接 WebSocket。将重定向到登录页面。");
        window.location.href = '/login';
        return;
    }
    
    // 修改: 确保在 URL 中正确地包含端口号
    const wsURL = `${wsProtocol}://${wsHost}${wsPort ? `:${wsPort}` : ''}/ws`;
    console.log(`正在尝试连接到 ${wsURL}...`);
    try {
        socket = new WebSocket(wsURL);
    } catch (e) {
        console.error("创建 WebSocket 失败:", e);
        ui.showNotificationBar(`WebSocket URL 无效: ${wsURL}`, true);
        return;
    }


    socket.onopen = () => {
        console.log('应用 WebSocket 连接成功。');
        startHeartbeat();
        if (onOpen) {
            onOpen();
        }
    };

    socket.onmessage = onMessage;

    socket.onclose = () => {
        const store = getStore();
        console.log(`应用 WebSocket 已断开。`);
        stopHeartbeat();
        if (onClose) {
            onClose(store.isManualDisconnect);
        }
        if (store.isManualDisconnect) {
            store.isManualDisconnect = false;
        }
    };

    socket.onerror = (error) => {
        console.error('应用 WebSocket 发生错误:', error);
        if (onError) {
            onError(error);
        }
    };
}

export function sendMessageToServer(message) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(message));
    } else {
        console.error("WebSocket 未连接，无法发送消息:", message);
    }
}

function startHeartbeat() {
    if (heartbeatInterval) clearInterval(heartbeatInterval);
    heartbeatInterval = setInterval(() => {
    }, 25000);
}

function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}