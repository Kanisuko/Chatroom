// web/static/js/state.js

// 定义一个集中的状态对象
const state = {
    currentUser: {
        id: null, // 添加
        username: null,
        display_name: null,
        avatar_url: null,
        status: 'offline',
        roles: [],
        isMicrophoneMuted: false,
        isHeadphoneMuted: false,
    },
    currentChannel: null, // 存储当前频道对象 {id, name, topic}
    pendingMessages: {},
    isManualDisconnect: false,
    reconnectAttempts: 0,
    reconnectTimer: null,
    allKnownUsers: {} // 存储所有已知用户的 profile
};

// 导出一个函数，允许其他模块访问和修改状态
export function getStore() {
    return state;
}