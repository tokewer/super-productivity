// ==UserScript==
// @name         Super Productivity 网页增强与本地自动备份助手
// @namespace    https://github.com/tokewer/super-productivity
// @version      1.0.0
// @description  为 Super Productivity 网页版提供持续的本地高可靠自动备份、迷你计时窗口状态同步与后台保活
// @author       tokewer
// @match        https://*.github.io/*
// @match        https://app.super-productivity.com/*
// @match        http://localhost:*/*
// @match        http://127.0.0.1:*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // Only activate if this page is Super Productivity
  const isSuperProductivity = () => {
    return !!(
      document.querySelector('body.super-productivity') ||
      document.querySelector('main-header') ||
      document.querySelector('tag-list') ||
      document.title.includes('Super Productivity') ||
      window.location.href.includes('super-productivity')
    );
  };

  const DEFAULT_BRIDGE_URL = 'http://127.0.0.1:4567';
  let bridgeUrl = GM_getValue('sp_bridge_url', DEFAULT_BRIDGE_URL);
  let authToken = GM_getValue('sp_bridge_token', '');
  let lastBackupEpoch = 0;
  const BACKUP_INTERVAL_MS = 15 * 60 * 1000; // 15 mins default
  let isBackingUp = false;

  // Auto-read token from URL hash if provided
  if (window.location.hash) {
    try {
      const hashParams = new URLSearchParams(window.location.hash.substring(1));
      const token = hashParams.get('bridge_token');
      const port = hashParams.get('bridge_port');
      if (token) {
        authToken = token.trim();
        GM_setValue('sp_bridge_token', authToken);
      }
      if (port) {
        bridgeUrl = `http://127.0.0.1:${port.trim()}`;
        GM_setValue('sp_bridge_url', bridgeUrl);
      }
    } catch (e) {}
  }

  // Cross-origin request abstraction
  const sendRequest = (method, path, data = null) => {
    const url = `${bridgeUrl}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      'X-Bridge-Token': authToken
    };

    return new Promise((resolve, reject) => {
      if (typeof GM_xmlhttpRequest !== 'undefined') {
        GM_xmlhttpRequest({
          method,
          url,
          headers,
          data: data ? JSON.stringify(data) : undefined,
          timeout: 10000,
          onload: (res) => {
            if (res.status >= 200 && res.status < 300) {
              try {
                resolve(JSON.parse(res.responseText));
              } catch (e) {
                resolve(res.responseText);
              }
            } else {
              reject(new Error(`HTTP ${res.status}: ${res.responseText}`));
            }
          },
          onerror: (err) => reject(err),
          ontimeout: () => reject(new Error('Bridge request timeout'))
        });
      } else {
        // Fallback to native fetch
        fetch(url, {
          method,
          headers,
          body: data ? JSON.stringify(data) : undefined
        })
          .then((res) => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
          })
          .then(resolve)
          .catch(reject);
      }
    });
  };

  // State Extractor from DOM & UI
  const getActiveTaskInfo = () => {
    // Check main play/pause button in header
    const playBtn = document.querySelector('button.play-btn') ||
                    document.querySelector('main-header button[aria-label*="Track"]') ||
                    document.querySelector('main-header .tracking-btn');

    const isTracking = !!(
      playBtn && (
        playBtn.classList.contains('active') ||
        playBtn.classList.contains('is-tracking') ||
        playBtn.querySelector('mat-icon')?.textContent?.trim() === 'pause' ||
        document.body.classList.contains('is-tracking')
      )
    );

    // Get current task title
    let taskTitle = '无活跃任务';
    const activeTaskEl = document.querySelector('task.is-current') ||
                         document.querySelector('.current-task-title') ||
                         document.querySelector('task.current');

    if (activeTaskEl) {
      const titleSpan = activeTaskEl.querySelector('.task-title') ||
                        activeTaskEl.querySelector('.title') ||
                        activeTaskEl.querySelector('input[name="title"]');
      if (titleSpan) {
        taskTitle = titleSpan.value || titleSpan.textContent?.trim() || taskTitle;
      }
    } else {
      // Check header title or page title
      const headerTask = document.querySelector('main-header .current-task-title');
      if (headerTask) {
        taskTitle = headerTask.textContent?.trim() || taskTitle;
      }
    }

    // Time spent from header or active task
    let timeSpentMs = 0;
    const timeDisplayEl = document.querySelector('main-header .time') ||
                          document.querySelector('.current-task-time');
    if (timeDisplayEl) {
      const timeStr = timeDisplayEl.textContent?.trim();
      if (timeStr && timeStr.includes(':')) {
        const parts = timeStr.split(':').map(Number);
        if (parts.length === 2) {
          timeSpentMs = (parts[0] * 60 + parts[1]) * 1000;
        } else if (parts.length === 3) {
          timeSpentMs = (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000;
        }
      }
    }

    return {
      activeTaskId: null,
      activeTaskTitle: taskTitle,
      timeSpentMs,
      isTracking,
      mode: 'task',
      lastTick: Date.now()
    };
  };

  // Full Database Snapshot Extractor from IndexedDB
  const exportFullAppData = async () => {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open('superProductivity');
      req.onerror = () => reject(new Error('Cannot open superProductivity IndexedDB'));
      req.onsuccess = (e) => {
        const db = e.target.result;
        const completeData = {};
        const storeNames = Array.from(db.objectStoreNames);

        if (storeNames.length === 0) {
          // If superProductivity uses pf-db or localStorage
          return resolve(exportFromLocalStorage());
        }

        const tx = db.transaction(storeNames, 'readonly');
        let remaining = storeNames.length;

        storeNames.forEach((storeName) => {
          const store = tx.objectStore(storeName);
          const allReq = store.getAll();
          allReq.onsuccess = () => {
            completeData[storeName] = allReq.result;
            remaining--;
            if (remaining === 0) {
              resolve(completeData);
            }
          };
          allReq.onerror = () => {
            remaining--;
            if (remaining === 0) resolve(completeData);
          };
        });
      };
    });
  };

  const exportFromLocalStorage = () => {
    const data = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith('SP_') || key.startsWith('SUP_') || key.includes('task') || key.includes('project'))) {
        try {
          data[key] = JSON.parse(localStorage.getItem(key));
        } catch {
          data[key] = localStorage.getItem(key);
        }
      }
    }
    return data;
  };

  // Trigger Local Backup
  const performBackup = async (source = 'auto_timer') => {
    if (isBackingUp) return;
    isBackingUp = true;
    updateBadge('⏳ 备份中...', '#ff9800');

    try {
      const payload = await exportFullAppData();
      if (!payload || Object.keys(payload).length === 0) {
        throw new Error('导出数据为空');
      }

      const res = await sendRequest('POST', '/api/backup', payload);
      lastBackupEpoch = Date.now();
      updateBadge('🛡 本地已备份', '#4caf50');
      console.log('[SuperProductivity Enhanced] Backup saved:', res.filename);
    } catch (err) {
      console.warn('[SuperProductivity Enhanced] Backup failed:', err);
      updateBadge('⚠ 备份失败', '#f44336');
    } finally {
      isBackingUp = false;
    }
  };

  // UI Enhancement Badge
  let badgeEl = null;
  const initUIBadge = () => {
    if (badgeEl) return;
    badgeEl = document.createElement('div');
    badgeEl.id = 'sp-bridge-status-badge';
    Object.assign(badgeEl.style, {
      position: 'fixed',
      bottom: '12px',
      right: '12px',
      zIndex: '999999',
      background: 'rgba(30, 30, 36, 0.92)',
      color: '#f4f4f6',
      fontSize: '11px',
      fontFamily: 'Segoe UI, -apple-system, sans-serif',
      padding: '5px 10px',
      borderRadius: '16px',
      border: '1px solid #444',
      boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
      cursor: 'pointer',
      userSelect: 'none',
      display: 'flex',
      alignItems: 'center',
      gap: '6px'
    });
    badgeEl.textContent = '○ 检查助手...';
    badgeEl.title = 'Super Productivity 本地增强助手\n点击配置或执行立即备份';

    badgeEl.addEventListener('click', () => {
      const currentToken = GM_getValue('sp_bridge_token', '');
      const newToken = prompt(
        '【Super Productivity 本地增强助手设置】\n\n请输入 config.json 中的 auth_token：',
        currentToken
      );
      if (newToken !== null) {
        GM_setValue('sp_bridge_token', newToken.trim());
        authToken = newToken.trim();
        performBackup('manual');
      }
    });

    document.body.appendChild(badgeEl);
  };

  const updateBadge = (text, color = '#4caf50') => {
    if (!badgeEl) return;
    badgeEl.textContent = text;
    badgeEl.style.borderColor = color;
  };

  // Periodic State Sync Loop (Every 1s)
  const startSyncLoop = () => {
    setInterval(async () => {
      const state = getActiveTaskInfo();
      try {
        await sendRequest('POST', '/api/state', state);

        // Consume queued actions from Mini Window
        const actionRes = await sendRequest('GET', '/api/action');
        if (actionRes?.action) {
          handleIncomingAction(actionRes.action);
        }
      } catch (e) {
        updateBadge('⚠ 助手离线', '#757575');
      }

      // Check auto backup interval
      if (Date.now() - lastBackupEpoch > BACKUP_INTERVAL_MS) {
        performBackup('interval');
      }
    }, 1200);
  };

  const handleIncomingAction = (act) => {
    if (act.action === 'toggle_tracking') {
      const playBtn = document.querySelector('button.play-btn') ||
                      document.querySelector('main-header button[aria-label*="Track"]') ||
                      document.querySelector('main-header .tracking-btn') ||
                      document.querySelector('task.is-current button.start-task-btn');
      if (playBtn) {
        playBtn.click();
      }
    } else if (act.action === 'trigger_backup') {
      performBackup('mini_window_trigger');
    }
  };

  // Reconcile Background Tab Throttling
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      // Tab woke up, immediately update state and sample time
      const state = getActiveTaskInfo();
      sendRequest('POST', '/api/state', state).catch(() => {});
    }
  });

  // Safety Backup before page unload
  window.addEventListener('beforeunload', () => {
    if (authToken) {
      exportFullAppData().then((payload) => {
        const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
        navigator.sendBeacon(`${bridgeUrl}/api/backup?token=${encodeURIComponent(authToken)}`, blob);
      }).catch(() => {});
    }
  });

  // Init when DOM ready
  const init = () => {
    initUIBadge();
    // Test initial connection
    sendRequest('GET', '/api/health')
      .then((res) => {
        updateBadge('🛡 助手已连接', '#4caf50');
        startSyncLoop();
        // First backup on start
        setTimeout(() => performBackup('session_start'), 3000);
      })
      .catch((err) => {
        updateBadge('○ 助手未启动', '#9e9e9e');
        startSyncLoop();
      });
  };

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
