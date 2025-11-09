// web/static/js/ui.js
// 重构为 UI 模块的入口和 DOM 管理器

import * as components from './components.js';

let dom = {};

export function initializeUI() {
    dom = {
        appContainer: document.querySelector('.app-container'),
        messagesContainer: document.querySelector('.chat__messages-container'),
        channelList: document.querySelector('.channel-list'),
        channelTitle: document.querySelector('.chat__header-title'),
        channelTopic: document.querySelector('.chat__header-topic'),
        userProfileDisplayName: document.getElementById('current-user-display-name'),
        userProfileUsernameTag: document.getElementById('current-user-username-tag'),
        userProfileAvatar: document.getElementById('current-user-avatar'),
        userProfileStatus: document.getElementById('current-user-status'),
        userListDiv: document.querySelector('.user-sidebar .user-list'),
        messageInput: document.querySelector('.chat__message-input'),
        createChannelModal: document.getElementById('create-channel-modal'),
        channelNameInput: document.getElementById('channel-name-input'),
        settingsModal: document.getElementById('settings-modal'),
        microphoneBtn: document.getElementById('microphone-btn'),
        headphonesBtn: document.getElementById('headphones-btn'),
        // 移除: screenshareBtn
        fileUploadInput: document.getElementById('file-upload-input'),
        toggleUserSidebarBtn: document.getElementById('toggle-user-sidebar-btn'),
        voiceStatusPanel: document.getElementById('voice-status-panel'),
        voiceStatusText: document.getElementById('voice-status-text'),
        voiceChannelName: document.getElementById('voice-channel-name'),
        // voiceRetryBtn 不再需要，合并到状态里
        remoteAudioContainer: document.getElementById('remote-audio-container'),
        streamContainer: document.getElementById('stream-container'),
        // 添加: 新的媒体控制按钮
        cameraBtn: document.getElementById('camera-btn'),
        screenshareBtn: document.getElementById('screenshare-btn'),
    };
}

// 重新导出所有 UI 函数，并将 dom 对象作为第一个参数传递
export const updateChannelList = (channels) => components.updateChannelList(dom, channels);
export const updateActiveChannelUI = (activeChannelName) => components.updateActiveChannelUI(activeChannelName);
export const addMessageToChat = (msg, options) => components.addMessageToChat(dom, msg, options);
export const addSystemMessage = (content) => components.addSystemMessage(dom, content);
export const addFileUploadCard = (file, uploadId) => components.addFileUploadCard(dom, file, uploadId);
export const clearChatArea = () => components.clearChatArea(dom);
export const updateChannelInfo = (id, name, topic) => components.updateChannelInfo(dom, id, name, topic);
export const updateUserList = (allRegisteredUsersInfo) => components.updateUserList(dom, allRegisteredUsersInfo);
export const updateUserProfile = (...args) => components.updateUserProfile(dom, ...args);
export const updateMicrophoneUI = (isMuted, isDisabled) => components.updateMicrophoneUI(dom, isMuted, isDisabled);
export const updateHeadphoneUI = (isMuted, isDisabled) => components.updateHeadphoneUI(dom, isMuted, isDisabled);
export const showNotificationBar = (message, isError) => components.showNotificationBar(message, isError);
export const hideNotificationBar = () => components.hideNotificationBar();
export const enableMessageInput = () => components.enableMessageInput(dom);
export const disableMessageInput = () => components.disableMessageInput(dom);
export const resetMessageInput = () => components.resetMessageInput(dom);
export const showCreateChannelModal = () => components.showCreateChannelModal(dom);
export const hideCreateChannelModal = () => components.hideCreateChannelModal(dom);
export const getNewChannelName = () => components.getNewChannelName(dom);
export const showSettingsModal = () => components.showSettingsModal(dom);
export const hideSettingsModal = () => components.hideSettingsModal(dom);
export const triggerFileUpload = () => components.triggerFileUpload(dom);

export const handleLogout = () => components.handleLogout();
export const toggleUserSidebar = () => components.toggleUserSidebar(dom);
export const applyUserSidebarPreference = () => components.applyUserSidebarPreference(dom);

export const toggleMicrophoneMute = () => components.toggleMicrophoneMute(dom);
export const toggleHeadphoneMute = () => components.toggleHeadphoneMute(dom);

export const showVoiceStatusPanel = (channelName) => components.showVoiceStatusPanel(dom, channelName);
export const hideVoiceStatusPanel = () => components.hideVoiceStatusPanel(dom);
export const updateVoiceStatus = (status, message) => components.updateVoiceStatus(dom, status, message); 
export const updateScreenshareUI = (isSharing) => components.updateScreenshareUI(dom, isSharing);