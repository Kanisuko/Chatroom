// web/static/js/components.js
// 包含所有独立的 UI 组件更新函数
import { getStore } from './state.js';

// --- 常量 ---
const DEFAULT_AVATAR = '/static/assets/default_avatar.png';
const ROLE_ORDER = ["SuperUser", "Owner", "Operator", "Moderator", "Member"];
const MESSAGE_GROUPING_THRESHOLD_MINUTES = 10;

// --- SVG 图标 ---
const fileIconSVG = `
<svg class="file-upload-card__icon" aria-hidden="true" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512">
    <path fill="currentColor" d="M224 136V0H24C10.7 0 0 10.7 0 24v464c0 13.3 10.7 24 24 24h336c13.3 0 24-10.7 24-24V160H248c-13.2 0-24-10.8-24-24zm64 236c0 6.6-5.4 12-12 12H108c-6.6 0-12-5.4-12-12v-8c0-6.6 5.4-12 12-12h168c6.6 0 12 5.4 12 12v8zm0-64c0 6.6-5.4 12-12 12H108c-6.6 0-12-5.4-12-12v-8c0-6.6 5.4-12 12-12h168c6.6 0 12 5.4 12 12v8zm0-72v8c0 6.6-5.4 12-12 12H108c-6.6 0-12-5.4-12-12v-8c0-6.6 5.4-12 12-12h168c6.6 0 12 5.4 12 12zm96-114.9L256 0v128h128z"></path>
</svg>`;


// --- 私有辅助函数 ---
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// --- 导出的 UI 更新函数 ---

// Channel List Components
export function updateChannelList(dom, channels) {
    const header = dom.channelList.querySelector('.channel-list__header');
    dom.channelList.innerHTML = '';
    if (header) {
        dom.channelList.appendChild(header);
    }
    
    if (!channels) {
        return;
    }

    channels.forEach(channel => {
        const channelItem = document.createElement('div');
        channelItem.classList.add('channel-list__item');
        channelItem.dataset.channel = channel.name;
        channelItem.dataset.channelId = channel.id; 
        channelItem.dataset.channelType = channel.type; 
        
        const iconClass = channel.type === 'voice' ? 'fas fa-volume-up' : 'fas fa-hashtag';

        channelItem.innerHTML = `
            <i class="channel-list__item-icon ${iconClass}"></i>
            <span class="channel-list__item-name">${channel.name}</span>`;
        dom.channelList.appendChild(channelItem);
    });
}

export function updateActiveChannelUI(activeChannelName) {
    document.querySelectorAll('.channel-list__item').forEach(item => { 
        item.classList.remove('channel-list__item--active'); 
        if (item.dataset.channel === activeChannelName) {
            item.classList.add('channel-list__item--active'); 
        }
    });
}

// Chat Area Components
function createFileMessageHTML(fileData) {
    return `
        <div class="file-message">
            <div class="file-message__icon">${fileIconSVG}</div>
            <div class="file-message__info">
                <a href="${fileData.url}" class="file-message__filename" target="_blank" download>${fileData.name}</a>
                <div class="file-message__meta">${formatBytes(fileData.size)}</div>
            </div>
            <div class="file-message__actions">
                <a href="${fileData.url}" class="file-message__action-btn" download aria-label="下载文件">
                    <i class="fas fa-download"></i>
                </a>
            </div>
        </div>`;
}

export function addMessageToChat(dom, msg, options = {}) {
    const store = getStore();
    const { isHistory = false, status = 'sent' } = options;
    
    const senderUsername = msg.sender_username || msg.username || '未知用户';
    const senderDisplayName = msg.sender_display_name || msg.sender || senderUsername;
    const content = msg.message || msg.content || '';
    const timestamp = msg.timestamp;
    
    const senderProfile = store.allKnownUsers[senderUsername.toLowerCase()];
    const avatarUrl = msg.avatar_url || senderProfile?.avatar_url || DEFAULT_AVATAR;

    const isSelf = senderUsername === store.currentUser.username;
    
    const messageItem = document.createElement('div');
    messageItem.classList.add('message');
    if (isSelf) {
        messageItem.classList.add('message--self');
    }
    if (status === 'sending') {
        messageItem.classList.add('message--sending');
    }
    messageItem.dataset.senderUsername = senderUsername;
    messageItem.dataset.timestamp = timestamp;
    
    let timeString = '...';
    let messageDate = null;
    if (timestamp) {
        try {
            messageDate = new Date(timestamp);
            timeString = isHistory 
                ? messageDate.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
                : messageDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {}
    }

    const lastMessageElement = dom.messagesContainer.firstElementChild;

    if (messageDate) {
        let lastMessageDate = null;
        if (lastMessageElement && lastMessageElement.dataset.timestamp) {
            lastMessageDate = new Date(lastMessageElement.dataset.timestamp);
        }

        if (!lastMessageDate || lastMessageDate.toLocaleDateString() !== messageDate.toLocaleDateString()) {
            const dateSeparator = document.createElement('div');
            dateSeparator.classList.add('date-separator');
            dateSeparator.innerHTML = `<span class="date-separator__text">${messageDate.toLocaleDateString([], { month: 'long', day: 'numeric', year: 'numeric' })}</span>`;
            dom.messagesContainer.prepend(dateSeparator);
        }
    }

    let isCompact = false;
    if (lastMessageElement && lastMessageElement.classList.contains('message')) {
        const lastSender = lastMessageElement.dataset.senderUsername;
        const lastTimestamp = lastMessageElement.dataset.timestamp;

        if (lastSender === senderUsername && lastTimestamp && messageDate) {
            const lastMessageDate = new Date(lastTimestamp);
            const timeDiffMinutes = (messageDate - lastMessageDate) / (1000 * 60);
            if (timeDiffMinutes < MESSAGE_GROUPING_THRESHOLD_MINUTES) {
                isCompact = true;
                messageItem.classList.add('message--compact');
            }
        }
    }

    let messageContentHTML = '';
    try {
        const parsedContent = JSON.parse(content);
        if (parsedContent.type === 'file') {
            messageContentHTML = createFileMessageHTML(parsedContent);
        } else {
            const sanitizedContent = content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            messageContentHTML = `<div class="message__text">${sanitizedContent}</div>`;
        }
    } catch (e) {
        const sanitizedContent = content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, '<br>');
        messageContentHTML = `<div class="message__text">${sanitizedContent}</div>`;
    }

    messageItem.innerHTML = `
        <div class="message__avatar-wrapper">
            <img src="${avatarUrl}" alt="${senderDisplayName} Avatar" class="message__avatar">
        </div>
        <div class="message__content-wrapper">
            <div class="message__info">
                <span class="message__display-name">${senderDisplayName}</span>
                <span class="message__timestamp">${timeString}</span>
            </div>
            ${messageContentHTML}
        </div>
        <div class="message__actions">
            <button class="message-actions__btn" aria-label="添加反应"><i class="fas fa-smile"></i></button>
            <button class="message-actions__btn" aria-label="回复"><i class="fas fa-reply"></i></button>
            <button class="message-actions__btn" aria-label="更多"><i class="fas fa-ellipsis-h"></i></button>
        </div>`;
    
    dom.messagesContainer.prepend(messageItem);
    
    if (status === 'sending' && msg.client_msg_id) {
        store.pendingMessages[msg.client_msg_id] = messageItem;
    }
}

export function addSystemMessage(dom, content) {
    const systemMessageItem = document.createElement('div');
    systemMessageItem.classList.add('system-message');
    systemMessageItem.textContent = content;
    dom.messagesContainer.prepend(systemMessageItem);
}

export function addFileUploadCard(dom, file, uploadId) {
    const card = document.createElement('div');
    card.classList.add('message');
    card.dataset.uploadId = uploadId;

    card.innerHTML = `
        <div class="message__avatar-wrapper" style="visibility: hidden;"></div>
        <div class="message__content-wrapper">
            <div class="file-upload-card">
                ${fileIconSVG}
                <div class="file-upload-card__info">
                    <div class="file-upload-card__filename">${file.name}</div>
                    <div class="file-upload-card__progress-bar">
                        <div class="file-upload-card__progress"></div>
                    </div>
                </div>
                <button class="file-upload-card__cancel-btn" aria-label="取消上传">&times;</button>
            </div>
        </div>`;
    
    dom.messagesContainer.prepend(card);
    
    const progressEl = card.querySelector('.file-upload-card__progress');
    let width = 0;
    const interval = setInterval(() => {
        if (width >= 95) {
            clearInterval(interval);
        } else {
            width += Math.random() * 10;
            progressEl.style.width = Math.min(width, 95) + '%';
        }
    }, 200);

    card.querySelector('.file-upload-card__cancel-btn').onclick = () => {
        card.remove();
        showNotificationBar(`文件 '${file.name}' 的上传已取消。`, true);
    };
    
    return card;
}

export function clearChatArea(dom) {
    dom.messagesContainer.innerHTML = '';
}

export function updateChannelInfo(dom, id, name, topic) {
    const store = getStore();
    store.currentChannel = { id, name, topic }; 
    dom.channelTitle.textContent = name;
    dom.channelTopic.textContent = topic || '欢迎来到这个频道！';
}

// User List Components
function createUserListItem(user) {
    const userItem = document.createElement('div');
    userItem.classList.add('user-list__item');
    const avatarUrl = user.avatar_url || DEFAULT_AVATAR;
    const displayName = user.display_name || user.username;

    userItem.innerHTML = `
        <div class="user-list__item-avatar-wrapper">
            <img src="${avatarUrl}" alt="${displayName} Avatar" class="user-list__item-avatar">
            <span class="user-list__item-status user-list__item-status--${user.status}"></span>
        </div>
        <div class="user-list__item-name-wrapper">
            <span class="user-list__item-display-name">${displayName}</span>
        </div>`;
    return userItem;
}

function createUserListGroup(title, users) {
    const groupDiv = document.createElement('div');
    groupDiv.classList.add('user-list__group');
    groupDiv.innerHTML = `<h4 class="user-list__group-title">${title} - ${users.length}</h4>`;
    
    users.sort((a, b) => (a.display_name || a.username).localeCompare(b.display_name || b.username));
    
    users.forEach(user => {
        groupDiv.appendChild(createUserListItem(user));
    });
    
    return groupDiv;
}

export function updateUserList(dom, allRegisteredUsersInfo) {
    const store = getStore();
    dom.userListDiv.innerHTML = '';
    
    store.allKnownUsers = {};
    if (allRegisteredUsersInfo) {
        allRegisteredUsersInfo.forEach(userInfo => {
            if (userInfo && userInfo.username) {
                store.allKnownUsers[userInfo.username.toLowerCase()] = {
                    id: userInfo.id,
                    username: userInfo.username,
                    display_name: userInfo.display_name || userInfo.username,
                    avatar_url: userInfo.avatar_url,
                    roles: userInfo.roles || [],
                    status: userInfo.status || 'offline'
                };
            }
        });
    }

    const groupedUsers = {};
    ROLE_ORDER.forEach(role => {
        groupedUsers[role] = { online: [], offline: [] };
    });

    Object.values(store.allKnownUsers).forEach(user => {
        const mainRole = (user.roles && user.roles.length > 0) ? user.roles[0] : 'Member';
        const effectiveRole = ROLE_ORDER.includes(mainRole) ? mainRole : 'Member';
        
        if (user.status === 'online') {
            groupedUsers[effectiveRole].online.push(user);
        } else {
            groupedUsers[effectiveRole].offline.push(user);
        }
    });

    ROLE_ORDER.forEach(roleName => {
        const group = groupedUsers[roleName];
        if (group.online.length > 0) {
            dom.userListDiv.appendChild(createUserListGroup(roleName, group.online));
        }
        if (group.offline.length > 0) {
            dom.userListDiv.appendChild(createUserListGroup(`${roleName} (离线)`, group.offline));
        }
    });
}

// User Panel Components
export function updateUserProfile(dom, id, username, displayName, avatarUrl, status, roles, isMicrophoneMuted, isHeadphoneMuted) {
    const store = getStore();
    
    store.currentUser.id = id;
    store.currentUser.username = username;
    store.currentUser.display_name = displayName || username;
    store.currentUser.avatar_url = avatarUrl || DEFAULT_AVATAR;
    store.currentUser.status = status || 'offline';
    store.currentUser.roles = roles || [];
    store.currentUser.isMicrophoneMuted = isMicrophoneMuted || false;
    store.currentUser.isHeadphoneMuted = isHeadphoneMuted || false;

    if (username) {
        dom.userProfileDisplayName.textContent = store.currentUser.display_name;
        dom.userProfileUsernameTag.style.display = 'none'; 
        dom.userProfileAvatar.src = store.currentUser.avatar_url;
        dom.userProfileStatus.className = `user-panel__status user-panel__status--${store.currentUser.status}`;
        updateMicrophoneUI(dom, store.currentUser.isMicrophoneMuted, false);
        updateHeadphoneUI(dom, store.currentUser.isHeadphoneMuted, false);
    } else {
        dom.userProfileDisplayName.textContent = "未登录";
        dom.userProfileUsernameTag.style.display = 'none';
        dom.userProfileAvatar.src = DEFAULT_AVATAR;
        dom.userProfileStatus.className = `user-panel__status user-panel__status--offline`;
        updateMicrophoneUI(dom, true, true);
        updateHeadphoneUI(dom, true, true);
    }
}

export function updateMicrophoneUI(dom, isMuted, isDisabled = false) {
    if (!dom.microphoneBtn) return;
    dom.microphoneBtn.disabled = isDisabled;
    const icon = dom.microphoneBtn.querySelector('i');
    if (icon) {
        icon.className = isMuted ? 'fas fa-microphone-slash' : 'fas fa-microphone';
        dom.microphoneBtn.classList.toggle('user-panel__control-btn--muted', isMuted);
    }
}

export function updateHeadphoneUI(dom, isMuted, isDisabled = false) {
    if (!dom.headphonesBtn) return;
    dom.headphonesBtn.disabled = isDisabled;
    const icon = dom.headphonesBtn.querySelector('i');
    if (icon) {
        icon.className = isMuted ? 'fas fa-volume-mute' : 'fas fa-headphones';
        dom.headphonesBtn.classList.toggle('user-panel__control-btn--muted', isMuted);
    }
}

export function updateScreenshareUI(dom, isSharing) {
    if (!dom.screenshareBtn) return;
    dom.screenshareBtn.classList.toggle('voice-status-panel__control-btn--active', isSharing);
}

// General UI Components
export function showNotificationBar(message, isError = false) {
    let bar = document.getElementById('notification-bar');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'notification-bar';
        document.body.prepend(bar);
    }
    bar.textContent = message;
    bar.className = 'notification-bar';
    bar.classList.add(isError ? 'notification-bar--error' : 'notification-bar--info'); 
    bar.style.display = 'block';
    setTimeout(() => {
        if (bar) {
            bar.style.display = 'none';
        }
    }, 3000);
}

export function hideNotificationBar() {
    let bar = document.getElementById('notification-bar');
    if (bar) {
        bar.style.display = 'none';
    }
}

export function enableMessageInput(dom) { dom.messageInput.disabled = false; }
export function disableMessageInput(dom) { dom.messageInput.disabled = true; }
export function resetMessageInput(dom) {
    dom.messageInput.value = '';
    dom.messageInput.style.height = 'auto';
}

export function showCreateChannelModal(dom) {
    dom.createChannelModal.classList.add('modal--active'); 
    dom.channelNameInput.focus();
}
export function hideCreateChannelModal(dom) {
    dom.createChannelModal.classList.remove('modal--active'); 
    dom.channelNameInput.value = '';
}
export function getNewChannelName(dom) {
    return dom.channelNameInput.value.trim();
}

export function showSettingsModal(dom) {
    dom.settingsModal.classList.add('modal--active');
}
export function hideSettingsModal(dom) {
    dom.settingsModal.classList.remove('modal--active');
}

export function triggerFileUpload(dom) {
    if (dom.fileUploadInput) {
        dom.fileUploadInput.click();
    }
}

export function handleLogout() {
    const store = getStore();
    store.isManualDisconnect = true;
    
    document.cookie = 'session_token=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT';
    
    window.location.href = '/login';
}

export function toggleUserSidebar(dom) {
    if (!dom.appContainer || !dom.toggleUserSidebarBtn) return;

    const isHidden = dom.appContainer.classList.toggle('app-container--user-sidebar-hidden');
    dom.toggleUserSidebarBtn.classList.toggle('active', !isHidden);
    
    localStorage.setItem('user_sidebar_hidden', isHidden);
}

export function applyUserSidebarPreference(dom) {
    if (!dom.appContainer || !dom.toggleUserSidebarBtn) return;

    const isHidden = localStorage.getItem('user_sidebar_hidden') === 'true';
    
    dom.appContainer.classList.toggle('app-container--user-sidebar-hidden', isHidden);
    dom.toggleUserSidebarBtn.classList.toggle('active', !isHidden);
}


export function showVoiceStatusPanel(dom, channelName) {
    if (!dom.voiceStatusPanel) return;
    dom.voiceStatusPanel.style.display = 'flex';
    dom.voiceChannelName.textContent = channelName;
    dom.streamContainer.style.display = 'flex'; 
}

export function hideVoiceStatusPanel(dom) {
    if (!dom.voiceStatusPanel) return;
    dom.voiceStatusPanel.style.display = 'none';
    dom.streamContainer.style.display = 'none'; 
    dom.streamContainer.innerHTML = ''; 
    if(dom.remoteAudioContainer) {
        dom.remoteAudioContainer.innerHTML = ''; 
    }
}

// 修改: 移除重试按钮的逻辑
export function updateVoiceStatus(dom, status, message = '') {
    if (!dom.voiceStatusText) return;

    const statusMap = {
        'live': { text: '直播中', class: 'voice-status-panel__status-text--connected' },
        'connecting': { text: 'DTLS 连接中...', class: 'voice-status-panel__status-text--connecting' },
        'gathering': { text: '正在检查路径...', class: 'voice-status-panel__status-text--connecting' },
        'connected': { text: '语音已连接', class: 'voice-status-panel__status-text--connected' },
        'failed': { text: message || '连接失败', class: 'voice-status-panel__status-text--failed' },
        'mic_request': { text: '请求媒体权限...', class: 'voice-status-panel__status-text--connecting'},
        'mic_failed': { text: message || '媒体权限错误', class: 'voice-status-panel__status-text--failed' },
        'disconnected': { text: '已断开', class: 'voice-status-panel__status-text--disconnected' },
    };

    const newStatus = statusMap[status] || { text: message, class: 'voice-status-panel__status-text--disconnected' };

    Object.values(statusMap).forEach(s => {
        if(s.class) dom.voiceStatusText.classList.remove(s.class);
    });

    if(newStatus.class) {
        dom.voiceStatusText.classList.add(newStatus.class);
    }
    
    dom.voiceStatusText.textContent = newStatus.text;
}