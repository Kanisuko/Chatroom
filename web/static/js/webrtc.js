// web/static/js/webrtc.js
import { getStore } from './state.js';
import * as ui from './ui.js';
import { sendMessageToServer } from './app-websocket.js';

let moduleConfig = { debug: false }; 

const PEER_CONNECTION_CONFIG = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
    ]
};

// --- 模块内部状态 ---
let localStream = null;
let screenStream = null;
let peerConnection = null; 
let voiceState = {
    isConnected: false,
    channelId: null,
    channelName: null, 
    isMuted: false,
    isDeafened: false,
    isSharingScreen: false
};

// --- 调试日志工具 ---
function debugLog(...args) {
    if (moduleConfig.debug) {
        console.log('[WebRTC-Debug]', ...args);
    }
}

// --- 私有辅助函数 ---

function sendSignal(data) {
    debugLog(`发送信令:`, data.type);
    sendMessageToServer({
        type: "webrtc_signal",
        payload: { data: data }
    });
}

// --- 核心 WebRTC 逻辑 ---

async function startConnection() {
    debugLog("开始与 SFU 建立新连接...");
    if (peerConnection) {
        await peerConnection.close();
    }

    peerConnection = new RTCPeerConnection(PEER_CONNECTION_CONFIG);

    peerConnection.ontrack = (event) => {
        const stream = event.streams[0];
        debugLog(`收到远程轨道 (kind: ${event.track.kind}, stream.id: ${stream.id})`);

        // 修改: 健壮的远程媒体元素处理
        const kind = event.track.kind;
        const container = kind === 'audio' ? ui.dom.remoteAudioContainer : ui.dom.streamContainer;
        if (!container) return;

        let mediaElement = document.getElementById(`remote-${kind}-${stream.id}`);
        if (!mediaElement) {
            if (kind === 'video') {
                container.innerHTML = ''; // 一次只显示一个屏幕共享
            }
            mediaElement = document.createElement(kind);
            mediaElement.id = `remote-${kind}-${stream.id}`;
            mediaElement.autoplay = true;
            mediaElement.playsInline = true;
            container.appendChild(mediaElement);
        }
        
        // 即使元素已存在，也更新 srcObject，以防流发生变化
        mediaElement.srcObject = stream;
    };

    peerConnection.onconnectionstatechange = () => {
        debugLog(`与 SFU 的连接状态变为: ${peerConnection.connectionState}`);
        updateOverallConnectionStatus();
    };

    if (localStream) {
        localStream.getTracks().forEach(track => {
            peerConnection.addTrack(track, localStream);
        });
        debugLog("已将本地音频轨道添加到 PeerConnection");
    }

    peerConnection.addTransceiver('video', { direction: 'sendrecv' });

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    sendSignal({ type: 'offer', sdp: offer.sdp });
}


function updateOverallConnectionStatus() {
    if (!voiceState.isConnected || !peerConnection) return;
    const state = peerConnection.connectionState;

    if (state === 'connected') {
        ui.updateVoiceStatus(voiceState.isSharingScreen ? 'live' : 'connected');
    } else if (state === 'failed') {
        ui.updateVoiceStatus('failed');
    } else if (state === 'connecting' || state === 'checking') {
        ui.updateVoiceStatus('connecting', 'DTLS 连接中...');
    } else if (state === 'disconnected' || state === 'closed') {
        ui.updateVoiceStatus('disconnected');
    }
}

async function ensureMediaPermissions() {
    debugLog("确保媒体权限...");
    if (localStream) {
        return true;
    }

    ui.updateVoiceStatus('mic_request');
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const hasMicrophone = devices.some(device => device.kind === 'audioinput');
        if (!hasMicrophone) throw new Error("NoMicrophone");
        
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        debugLog("媒体权限获取成功", stream);
        localStream = stream; 
        return true;
    } catch (error) {
        debugLog("获取媒体失败:", error.name, error.message);
        let errorMessage = '麦克风权限被拒绝';
        if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError' || error.message === 'NoMicrophone') {
            errorMessage = '未检测到麦克风';
        } else if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            errorMessage = '麦克风权限被拒绝';
        }
        ui.updateVoiceStatus('mic_failed', errorMessage);
        localStream = null;
        return false;
    }
}

// --- 导出的公共函数 ---

export function initialize(appConfig) {
    moduleConfig = appConfig;
    debugLog("WebRTC 模块 (SFU 模式) 已初始化");
}

export async function joinVoiceChannel(channelId, channelName) {
    debugLog(`==> 开始加入语音频道 #${channelName} (SFU)`);
    
    if (voiceState.isConnected) {
        await leaveVoiceChannel();
    }
    
    const hasPermission = await ensureMediaPermissions();
    ui.showVoiceStatusPanel(channelName);
    
    // 即使没有麦克风权限，也继续加入（只听模式）
    sendMessageToServer({ type: "join_voice", payload: { channel_id: channelId } });
    voiceState.isConnected = true;
    voiceState.channelId = channelId;
    voiceState.channelName = channelName;
}

export async function leaveVoiceChannel() {
    debugLog(`==> 开始离开语音频道 (ID:${voiceState.channelId})`);
    if (!voiceState.isConnected) return;

    if (voiceState.isSharingScreen) {
        await toggleScreenShare(false); 
    }
    
    sendMessageToServer({ type: "leave_voice", payload: { channel_id: voiceState.channelId } });
    
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }

    if (peerConnection) {
        await peerConnection.close();
        peerConnection = null;
    }
    
    Object.assign(voiceState, {
        isConnected: false,
        channelId: null,
        channelName: null,
        isMuted: false,
        isDeafened: false,
        isSharingScreen: false
    });
    
    ui.hideVoiceStatusPanel();
    ui.updateMicrophoneUI(false, true);
    ui.updateHeadphoneUI(false, true);
    ui.updateScreenshareUI(false);
    debugLog("离开流程完成。");
}

export function toggleMute(forceState) {
    const newMuteState = (typeof forceState === 'boolean') ? forceState : !voiceState.isMuted;
    if (localStream && localStream.getAudioTracks().length > 0) {
        localStream.getAudioTracks()[0].enabled = !newMuteState;
        voiceState.isMuted = newMuteState;
        ui.updateMicrophoneUI(newMuteState);
        debugLog(`麦克风静音状态切换为: ${newMuteState}`);
    } else {
        debugLog("无法切换静音，localStream 或音轨不存在。");
        ui.showNotificationBar("无法控制麦克风，请检查权限。", true);
        ui.updateMicrophoneUI(voiceState.isMuted);
    }
}

export function toggleDeafen(forceState) {
    const newDeafenState = (typeof forceState === 'boolean') ? forceState : !voiceState.isDeafened;
    document.querySelectorAll('#remote-audio-container audio, #stream-container video').forEach(media => {
        media.muted = newDeafenState;
    });
    voiceState.isDeafened = newDeafenState;
    if (newDeafenState && !voiceState.isMuted) {
        toggleMute(true);
    }
    ui.updateHeadphoneUI(newDeafenState);
    debugLog(`耳机静音状态切换为: ${newDeafenState}`);
}

export async function toggleScreenShare(forceState) {
    const newSharingState = (typeof forceState === 'boolean') ? forceState : !voiceState.isSharingScreen;
    if (!peerConnection || !voiceState.isConnected) {
        debugLog("无法切换屏幕共享，未完全连接到语音频道。");
        return;
    }

    const videoSender = peerConnection.getSenders().find(s => s.track?.kind === 'video' || s.track === null);
    if (!videoSender) {
        console.error("错误: 找不到 video sender。无法共享屏幕。");
        return;
    }

    if (newSharingState) {
        try {
            const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
            if(screenStream) {
                screenStream.getTracks().forEach(track => track.stop());
            }
            screenStream = stream;
            const screenTrack = stream.getVideoTracks()[0];
            
            if (stream.getAudioTracks().length > 0) {
                const screenAudioTrack = stream.getAudioTracks()[0];
                peerConnection.addTrack(screenAudioTrack, stream);
                if (localStream) localStream.getAudioTracks()[0].enabled = false;
            }
            
            screenTrack.onended = () => {
                debugLog("用户通过浏览器UI停止了共享");
                if (voiceState.isSharingScreen) {
                    toggleScreenShare(false);
                }
            };
            
            await videoSender.replaceTrack(screenTrack);
            voiceState.isSharingScreen = true;
            debugLog("开始屏幕共享");
            
            const streamContainer = document.getElementById('stream-container');
            if (streamContainer) {
                streamContainer.innerHTML = '';
                const localVideo = document.createElement('video');
                localVideo.srcObject = stream;
                localVideo.muted = true; 
                localVideo.autoplay = true;
                localVideo.playsInline = true;
                streamContainer.appendChild(localVideo);
            }

        } catch(e) {
            debugLog("获取屏幕共享失败:", e);
            ui.showNotificationBar("无法开始屏幕共享。", true);
            voiceState.isSharingScreen = false;
        }
    } else {
        if (screenStream) {
            screenStream.getTracks().forEach(track => track.stop());
            screenStream = null;
        }
        await videoSender.replaceTrack(null);
        voiceState.isSharingScreen = false;
        
        if (localStream && localStream.getAudioTracks().length > 0) {
             localStream.getAudioTracks()[0].enabled = !voiceState.isMuted;
        }

        const streamContainer = document.getElementById('stream-container');
        if (streamContainer) streamContainer.innerHTML = '';
        debugLog("停止屏幕共享");
    }
    ui.updateScreenshareUI(voiceState.isSharingScreen);
    updateOverallConnectionStatus();
}

export function isInVoiceChannel() {
    return voiceState.isConnected;
}


export async function handleSignalingMessage(message) {
    const { type, payload } = message;
    
    debugLog(`处理信令: ${type}, payload:`, payload);

    switch (type) {
        case 'join_voice_success':
            await startConnection();
            ui.updateMicrophoneUI(voiceState.isMuted, false);
            ui.updateHeadphoneUI(voiceState.isDeafened, false);
            break;
            
        case 'webrtc_signal':
            if (!peerConnection) return;
            const data = payload.data;
            try {
                if (data && data.type === 'answer') {
                    debugLog("收到来自 SFU 的 answer");
                    await peerConnection.setRemoteDescription(new RTCSessionDescription(data));
                }
            } catch (error) {
                console.error(`[WebRTC] 处理信令时出错:`, error);
            }
            break;

        default:
            debugLog('警告: 收到未知的语音信令消息类型:', type);
    }
}