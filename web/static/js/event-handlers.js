// web/static/js/event-handlers.js
import { getStore } from './state.js';
import * as ui from './ui.js';
import { sendMessageToServer } from './app-websocket.js';
import * as api from './api.js';
import * as webrtc from './webrtc.js'; 

// --- Message Handlers ---
export function handleMessageSend(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const content = e.target.value.trim();
        const store = getStore();
        
        if (!store.currentUser.username) {
            ui.showNotificationBar("请先登录才能发送消息。", true);
            ui.resetMessageInput();
            return;
        }

        if (content) {
            const clientMsgId = `msg_${Date.now()}_${Math.random()}`;

            ui.addMessageToChat({
                sender_username: store.currentUser.username, 
                sender_display_name: store.currentUser.display_name,
                message: content,
                timestamp: new Date().toISOString(),
                client_msg_id: clientMsgId,
                avatar_url: store.currentUser.avatar_url 
            }, { status: 'sending' });

            sendMessageToServer({
                type: "chat_message",
                payload: { message: content, client_msg_id: clientMsgId }
            });
            
            ui.resetMessageInput();
        }
    }
}

// --- Channel Handlers ---
export function handleChannelJoin(e) {
    const channelItem = e.target.closest('.channel-list__item'); 
    if (channelItem) {
        const channelName = channelItem.dataset.channel;
        const channelId = parseInt(channelItem.dataset.channelId, 10); 
        const channelType = channelItem.dataset.channelType; 

        const store = getStore();
        if (!store.currentUser.username) {
            ui.showNotificationBar("请先登录才能加入频道。", true);
            return;
        }

        if (channelName && !isNaN(channelId) && channelType) {
            if (channelType === 'voice') {
                webrtc.joinVoiceChannel(channelId, channelName);
            } else {
                webrtc.leaveVoiceChannel();
                sendMessageToServer({ type: "command", payload: { command: "join", args: [channelName] } });
            }
        }
    }
}

export function handleCreateChannel() {
    const channelName = ui.getNewChannelName();
    const store = getStore();
    if (!store.currentUser.username) {
        ui.showNotificationBar("请先登录才能创建频道。", true);
        ui.hideCreateChannelModal(); 
        return;
    }

    if (channelName && channelName.length >= 2 && channelName.length <= 20) {
        const channelTypeInput = document.querySelector('input[name="channel-type"]:checked');
        const channelType = channelTypeInput ? channelTypeInput.value : 'text';

        const command = channelType === 'voice' ? 'createvoicechannel' : 'createchannel';
        
        sendMessageToServer({
            type: "command",
            payload: {
                command: command,
                args: [channelName]
            }
        });
        ui.hideCreateChannelModal();
    } else {
        ui.showNotificationBar("频道名称必须为2-20个字符！", true); 
    }
}

// --- Upload Handlers ---
export async function handleAvatarUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const store = getStore();
    if (!store.currentUser.username) {
        ui.showNotificationBar("请先登录才能上传头像。", true);
        e.target.value = ''; 
        return;
    }

    if (file.size > 2 * 1024 * 1024) {
        ui.showNotificationBar('文件大小不能超过 2MB', true); 
        return;
    }
    if (!['image/jpeg', 'image/png', 'image/gif'].includes(file.type)) {
        ui.showNotificationBar('只支持上传 JPG, PNG, GIF 格式的图片', true); 
        return;
    }

    await api.uploadAvatar(file);
    e.target.value = '';
}

export async function handleFileUpload(e) { 
    const file = e.target.files[0];
    if (!file) return;

    const store = getStore();
    if (!store.currentUser.username || !store.currentChannel) {
        ui.showNotificationBar("请先登录并加入频道才能上传文件。", true);
        e.target.value = '';
        return;
    }

    const maxFileSize = 50 * 1024 * 1024;
    if (file.size > maxFileSize) {
        ui.showNotificationBar(`文件大小不能超过 ${maxFileSize / (1024 * 1024)}MB`, true);
        e.target.value = '';
        return;
    }

    const clientMsgId = `upload_${Date.now()}_${Math.random()}`;
    const uploadCard = ui.addFileUploadCard(file, clientMsgId);
    store.pendingMessages[clientMsgId] = uploadCard;
    
    const success = await api.uploadFile(file, store.currentChannel.id, clientMsgId);

    if (!success) {
        uploadCard.remove();
        delete store.pendingMessages[clientMsgId];
    }
    
    e.target.value = ''; 
}

// --- Sidebar/User Panel Handlers ---
export function handleLogout() {
    ui.handleLogout();
}

export function handleToggleUserSidebar() {
    ui.toggleUserSidebar();
}

export function handleToggleMicrophoneMute() {
    if (!webrtc.isInVoiceChannel()) {
        ui.showNotificationBar("请先加入语音频道", true);
        return;
    }
    webrtc.toggleMute();
}

export function handleToggleHeadphoneMute() {
    if (!webrtc.isInVoiceChannel()) {
        ui.showNotificationBar("请先加入语音频道", true);
        return;
    }
    webrtc.toggleDeafen();
}

export function handleToggleScreenshare() {
    if (!webrtc.isInVoiceChannel()) {
        ui.showNotificationBar("请先加入语音频道才能共享屏幕", true);
        return;
    }
    webrtc.toggleScreenShare();
}

export function handleToggleCamera() {
    if (!webrtc.isInVoiceChannel()) {
        ui.showNotificationBar("请先加入语音频道才能开启摄像头", true);
        return;
    }
    ui.showNotificationBar("摄像头功能将在下一阶段实现。", false);
}


export function handleVoiceDisconnect() {
    webrtc.leaveVoiceChannel();
}