// web/static/js/api.js
// 封装所有 API fetch 请求

import { getAuthHeader } from './app-websocket.js';
import * as ui from './ui.js';

/**
 * 处理头像上传
 * @param {File} file - 用户选择的头像文件
 */
export async function uploadAvatar(file) {
    const formData = new FormData();
    formData.append('avatar', file);

    try {
        ui.showNotificationBar('正在上传头像...', false);
        
        const response = await fetch('/api/user/avatar', {
            method: 'POST',
            headers: getAuthHeader(),
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            ui.showNotificationBar('头像上传成功！', false);
            // 后端会通过 WebSocket 广播 user_list_update，UI 会自动更新
        } else {
            throw new Error(result.error || '上传失败');
        }
    } catch (error) {
        console.error('Avatar upload failed:', error);
        ui.showNotificationBar(`头像上传失败: ${error.message}`, true);
    }
}

/**
 * 处理通用文件上传
 * @param {File} file - 用户选择的文件
 * @param {number} channelId - 当前频道的 ID
 * @param {string} clientMsgId - 用于关联上传卡片的前端唯一 ID
 * @returns {Promise<boolean>} - 返回上传是否成功
 */
export async function uploadFile(file, channelId, clientMsgId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('channel_id', channelId);
    formData.append('client_msg_id', clientMsgId);

    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            headers: getAuthHeader(),
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || '上传失败');
        }
        return true; // 上传成功
    } catch (error) {
        console.error('File upload failed:', error);
        ui.showNotificationBar(`文件上传失败: ${error.message}`, true);
        return false; // 上传失败
    }
}