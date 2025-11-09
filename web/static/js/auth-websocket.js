// web/static/js/auth-websocket.js (原 websocket.js)
// 负责认证流程的 WebSocket 连接
import { getStore } from './state.js';

let socket;

export function connectWebSocket(authPayload) {
    if (socket && socket.readyState !== WebSocket.CLOSED) {
        socket.close();
    }
    
    // 修改: 从 window.location 获取主机和端口
    const wsProtocol = document.body.dataset.wsProtocol;
    const wsHost = window.location.hostname;
    const wsPort = window.location.port;
    const wsURL = `${wsProtocol}://${wsHost}${wsPort ? `:${wsPort}` : ''}/ws`;
    
    console.log(`正在尝试连接到 ${wsURL}...`);
    try {
        socket = new WebSocket(wsURL);
    } catch (e) {
        console.error("创建 WebSocket 失败:", e);
        import('./auth.js').then(auth => {
            auth.showGlobalAuthError(`WebSocket URL 无效: ${wsURL}`);
        });
        return;
    }


    socket.onopen = () => {
        console.log('WebSocket 连接成功。正在发送认证请求...');
        sendMessageToServer({ type: "auth_request", payload: authPayload });
    };

    socket.onmessage = handleAuthResponseMessage;

    socket.onclose = () => {
        console.log(`认证 WebSocket 已断开`);
    };

    socket.onerror = (error) => {
        console.error('认证 WebSocket 发生错误:', error);
        import('./auth.js').then(auth => {
            auth.showGlobalAuthError('无法连接到服务器。');
        });
    };
}

function handleAuthResponseMessage(event) {
    const message = JSON.parse(event.data);
    console.log('收到认证响应:', message);

    import('./auth.js').then(auth => {
        switch (message.type) {
            case 'auth_success':
                const { user, token } = message.payload;
                if (user && token) {
                    auth.dispatchAuthSuccess(token);
                } else {
                    auth.showAuthSuccessMessageInModal(message.payload.message);
                }
                break;
            case 'auth_failure':
                auth.showGlobalAuthError(message.payload.message);
                break;
            default:
                console.warn('收到未知的认证响应类型:', message.type);
        }
    });
}

export function sendMessageToServer(message) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(message));
    }
}