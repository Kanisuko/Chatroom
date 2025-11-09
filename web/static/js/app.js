// web/static/js/app.js
import { getStore } from './state.js';
import * as ui from './ui.js';
import { connectAppWebSocket, sendMessageToServer } from './app-websocket.js';
import * as handlers from './event-handlers.js';
import * as webrtc from './webrtc.js'; 

const isDebugMode = (new URLSearchParams(window.location.search)).get('debug') === 'true';
const config = {
    debug: isDebugMode
};

export { config };

// --- WebSocket 消息处理器 ---
function handleAppWebSocketMessage(event) {
    const store = getStore();
    const message = JSON.parse(event.data);

    if (config.debug) {
        console.log('RECV:', message);
    }
    
    const voiceSignalTypes = [
        'join_voice_success',
        'user_joined_voice',
        'user_left_voice',
        'webrtc_signal'
    ];
    if (voiceSignalTypes.includes(message.type)) {
        webrtc.handleSignalingMessage(message);
        return; 
    }

    switch (message.type) {
        case 'auth_success':
            const { user } = message.payload;
            if (user) {
                ui.hideNotificationBar();
                store.reconnectAttempts = 0;
                clearTimeout(store.reconnectTimer);
                ui.enableMessageInput();
                
                ui.updateUserProfile(
                    user.id,
                    user.username,
                    user.display_name,
                    user.avatar_url,
                    user.status,
                    user.roles,
                    store.currentUser.isMicrophoneMuted,
                    store.currentUser.isHeadphoneMuted
                );
            }
            break;
        case 'auth_failure':
            console.error("会话恢复失败:", message.payload.message);
            document.cookie = 'session_token=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT';
            window.location.href = '/login';
            break;
        case 'chat_broadcast':
            const { client_msg_id } = message.payload;
            if (client_msg_id && store.pendingMessages[client_msg_id]) {
                const uploadCard = store.pendingMessages[client_msg_id];
                ui.addMessageToChat(message.payload);
                uploadCard.remove();
                delete store.pendingMessages[client_msg_id];
            } else {
                ui.addMessageToChat(message.payload);
            }
            break;
        case 'system_message':
            ui.addSystemMessage(message.payload.message);
            break;
        case 'user_list_update':
            ui.updateUserList(message.payload.users);
            break;
        case 'channel_list_update':
            ui.updateChannelList(message.payload.channels);
            break;
        case 'join_channel_success':
            ui.clearChatArea();
            ui.updateChannelInfo(message.payload.channel_id, message.payload.channel_name, message.payload.channel_topic);
            ui.updateActiveChannelUI(message.payload.channel_name);

            if (message.payload.users) {
                ui.updateUserList(message.payload.users);
            }

            if (message.payload.history && Array.isArray(message.payload.history)) {
                message.payload.history.forEach(msg => ui.addMessageToChat(msg, { isHistory: true }));
            }
            break;
        case 'error_message':
            ui.showNotificationBar(`服务器错误: ${message.payload.message}`, true);
            break;
        default:
            console.warn('收到未知的应用消息类型:', message.type);
    }
}

function handleAppWebSocketOpen() {
    const store = getStore();
    const token = document.cookie.split('; ').find(row => row.startsWith('session_token='))?.split('=')[1];
    
    store.reconnectAttempts = 0;
    clearTimeout(store.reconnectTimer);
    ui.hideNotificationBar();
    
    console.log('正在请求恢复会话...');
    sendMessageToServer({ type: "auth_request", payload: { action: "resume", token: token } });
}

function handleAppWebSocketClose(isManualDisconnect) {
    const store = getStore();
    const MAX_RECONNECT_ATTEMPTS = 5;

    if (isManualDisconnect) {
        console.log("手动断开，不进行重连。");
        return;
    }

    ui.disableMessageInput();
    webrtc.leaveVoiceChannel();

    if (store.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        ui.showNotificationBar("无法连接到服务器，请手动刷新。", true);
        return;
    }

    store.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, store.reconnectAttempts - 1), 30000);
    ui.showNotificationBar(`连接已断开，${delay / 1000}秒后尝试重连... (${store.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`, true);

    clearTimeout(store.reconnectTimer);
    store.reconnectTimer = setTimeout(initializeWebSocket, delay);
}

function initializeWebSocket() {
    connectAppWebSocket({
        onOpen: handleAppWebSocketOpen,
        onMessage: handleAppWebSocketMessage,
        onClose: handleAppWebSocketClose,
        onError: (error) => {
            console.error("WebSocket 连接出错:", error);
            ui.showNotificationBar("WebSocket 连接发生错误。", true);
        }
    });
}

function initializeEventHandlers() {
    const messageInput = document.querySelector('.chat__message-input'); 
    messageInput.addEventListener('keydown', handlers.handleMessageSend);
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = `${messageInput.scrollHeight}px`;
    });
    
    const channelList = document.querySelector('.channel-list'); 
    channelList.addEventListener('click', handlers.handleChannelJoin);

    const userSettingsBtn = document.getElementById('user-settings-btn');
    if (userSettingsBtn) { 
        userSettingsBtn.addEventListener('click', ui.showSettingsModal); 
    }
    
    const avatarImg = document.getElementById('current-user-avatar');
    const avatarUploadInput = document.getElementById('avatar-upload-input');
    
    if (avatarImg) { 
        avatarImg.addEventListener('click', () => {
            if (getStore().currentUser.username) {
                avatarUploadInput.click();
            } else {
                ui.showNotificationBar("请先登录才能上传头像。", true); 
            }
        });
    }
    if (avatarUploadInput) { 
        avatarUploadInput.addEventListener('change', handlers.handleAvatarUpload);
    }

    const addChannelBtn = document.getElementById('add-channel-btn'); 
    if (addChannelBtn) { 
        addChannelBtn.addEventListener('click', () => {
            if (getStore().currentUser.username) {
                ui.showCreateChannelModal();
            } else {
                ui.showNotificationBar("请先登录才能创建频道。", true);
            }
        });
    }

    const createChannelCancelBtn = document.getElementById('create-channel-cancel-btn');
    if (createChannelCancelBtn) { 
        createChannelCancelBtn.addEventListener('click', ui.hideCreateChannelModal);
    }

    const createChannelConfirmBtn = document.getElementById('create-channel-confirm-btn');
    if (createChannelConfirmBtn) { 
        createChannelConfirmBtn.addEventListener('click', handlers.handleCreateChannel);
    }

    const settingsModalCloseBtn = document.querySelector('#settings-modal .settings-modal__close-btn'); 
    if (settingsModalCloseBtn) {
        settingsModalCloseBtn.addEventListener('click', ui.hideSettingsModal);
    }
    const logoutBtn = document.getElementById('logout-btn'); 
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handlers.handleLogout);
    }

    const attachFileBtn = document.getElementById('attach-file-btn');
    if (attachFileBtn) {
        attachFileBtn.addEventListener('click', () => {
            const store = getStore();
            if (!store.currentUser.username) {
                ui.showNotificationBar("请先登录才能上传文件。", true);
                return;
            }
            if (!store.currentChannel) {
                ui.showNotificationBar("请先加入一个频道才能上传文件。", true);
                return;
            }
            ui.triggerFileUpload();
        });
    }
    const fileUploadInput = document.getElementById('file-upload-input'); 
    if (fileUploadInput) {
        fileUploadInput.addEventListener('change', handlers.handleFileUpload);
    }

    const microphoneBtn = document.getElementById('microphone-btn'); 
    if (microphoneBtn) {
        microphoneBtn.addEventListener('click', handlers.handleToggleMicrophoneMute);
    }
    const headphonesBtn = document.getElementById('headphones-btn'); 
    if (headphonesBtn) {
        headphonesBtn.addEventListener('click', handlers.handleToggleHeadphoneMute);
    }

    const toggleUserSidebarBtn = document.getElementById('toggle-user-sidebar-btn');
    if (toggleUserSidebarBtn) {
        toggleUserSidebarBtn.addEventListener('click', handlers.handleToggleUserSidebar);
    }
    
    const voiceDisconnectBtn = document.getElementById('voice-disconnect-btn');
    if (voiceDisconnectBtn) {
        voiceDisconnectBtn.addEventListener('click', handlers.handleVoiceDisconnect);
    }

    // 添加: 绑定新的媒体控制按钮事件
    const cameraBtn = document.getElementById('camera-btn');
    if (cameraBtn) {
        cameraBtn.addEventListener('click', handlers.handleToggleCamera);
    }

    const screenshareBtn = document.getElementById('screenshare-btn');
    if (screenshareBtn) {
        screenshareBtn.addEventListener('click', handlers.handleToggleScreenshare);
    }
}

// --- 初始化流程 ---
document.addEventListener('DOMContentLoaded', () => {
    ui.initializeUI();
    webrtc.initialize(config);
    initializeWebSocket();
    initializeEventHandlers(); 
    ui.applyUserSidebarPreference();
});