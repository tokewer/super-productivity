import { DestroyRef, inject, Injectable } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { TaskService } from '../../features/tasks/task.service';
import { StateSnapshotService } from '../../op-log/backup/state-snapshot.service';
import { AppDataComplete } from '../../op-log/model/model-config';
import { hasMeaningfulStateData } from '../../op-log/validation/has-meaningful-state-data.util';
import { Log } from '../log';
import { IS_ELECTRON } from '../../app.constants';
import { combineLatest, interval } from 'rxjs';
import { filter, throttleTime } from 'rxjs/operators';

const BRIDGE_DEFAULT_URL = 'http://127.0.0.1:4567';
const STATE_SYNC_INTERVAL_MS = 1200;
const AUTO_BACKUP_INTERVAL_MS = 15 * 60 * 1000;

@Injectable({
  providedIn: 'root',
})
export class LocalBridgeService {
  private _destroyRef = inject(DestroyRef);
  private _taskService = inject(TaskService);
  private _stateSnapshotService = inject(StateSnapshotService);

  private _bridgeUrl = BRIDGE_DEFAULT_URL;
  private _authToken = '';
  private _isOnline = false;
  private _isBackingUp = false;
  private _currentTask: any = null;

  get isOnline(): boolean {
    return this._isOnline;
  }

  init(): void {
    // Only activate in browser / web environments (Electron already has native IPC)
    if (IS_ELECTRON) {
      return;
    }

    this._loadSettings();
    this._probeBridge();

    // 1. Live Task & Timer Sync
    combineLatest([
      this._taskService.currentTask$,
      this._taskService.currentTaskId$,
      this._taskService.currentTaskProgress$,
    ])
      .pipe(
        throttleTime(STATE_SYNC_INTERVAL_MS, undefined, { leading: true, trailing: true }),
        takeUntilDestroyed(this._destroyRef),
      )
      .subscribe(([currentTask, currentTaskId]) => {
        this._currentTask = currentTask;
        this._sendCurrentState(currentTask, !!currentTaskId);
      });

    // 2. Action Polling (for Mini Window control commands)
    interval(1500)
      .pipe(
        filter(() => this._isOnline),
        takeUntilDestroyed(this._destroyRef),
      )
      .subscribe(() => {
        this._pollPendingActions();
      });

    // 3. Auto-reconnect probe: polls bridge every 4s if currently offline
    interval(4000)
      .pipe(
        filter(() => !this._isOnline),
        takeUntilDestroyed(this._destroyRef),
      )
      .subscribe(() => {
        this._probeBridge();
      });

    // 4. Periodic High-Reliability Auto-Backup (every 15 minutes)
    interval(AUTO_BACKUP_INTERVAL_MS)
      .pipe(
        filter(() => this._isOnline),
        takeUntilDestroyed(this._destroyRef),
      )
      .subscribe(() => {
        this.triggerBackup('auto_interval');
      });

    // 5. Tab visibility reconciliation
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden && this._isOnline) {
          this._sendCurrentState(this._currentTask, !!this._taskService.currentTaskId());
        }
      });
    }

    // 6. Final snapshot before browser tab unloads
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        this._sendBeaconBackup();
      });
    }
  }

  private _loadSettings(): void {
    try {
      if (typeof window !== 'undefined' && window.location.hash) {
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const token = params.get('bridge_token');
        const port = params.get('bridge_port');
        let updated = false;

        if (token) {
          this._authToken = token.trim();
          localStorage.setItem('SP_LOCAL_BRIDGE_TOKEN', this._authToken);
          params.delete('bridge_token');
          updated = true;
        }
        if (port) {
          this._bridgeUrl = `http://127.0.0.1:${port.trim()}`;
          localStorage.setItem('SP_LOCAL_BRIDGE_URL', this._bridgeUrl);
          params.delete('bridge_port');
          updated = true;
        }
        if (updated && window.history?.replaceState) {
          const rest = params.toString();
          const cleanUrl = window.location.pathname + (rest ? `#${rest}` : '');
          window.history.replaceState(null, '', cleanUrl);
        }
      }

      this._bridgeUrl =
        localStorage.getItem('SP_LOCAL_BRIDGE_URL') || BRIDGE_DEFAULT_URL;
      if (!this._authToken) {
        this._authToken = localStorage.getItem('SP_LOCAL_BRIDGE_TOKEN') || '';
      }
    } catch {
      // Fallback
    }
  }

  setAuthToken(token: string): void {
    this._authToken = token.trim();
    try {
      localStorage.setItem('SP_LOCAL_BRIDGE_TOKEN', this._authToken);
    } catch {}
    this._probeBridge();
  }

  private async _probeBridge(): Promise<boolean> {
    try {
      const res = await fetch(`${this._bridgeUrl}/api/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data?.token && !this._authToken) {
          this._authToken = data.token;
          try {
            localStorage.setItem('SP_LOCAL_BRIDGE_TOKEN', data.token);
          } catch {}
        }
        this._isOnline = true;
        Log.log('LocalBridgeService: Connected to local bridge server');
        if (this._currentTask) {
          this._sendCurrentState(this._currentTask, !!this._taskService.currentTaskId());
        }
        return true;
      }
    } catch {
      this._isOnline = false;
    }
    return false;
  }

  private async _sendCurrentState(currentTask: any, isTracking: boolean = false): Promise<void> {
    if (!this._isOnline && !(await this._probeBridge())) {
      return;
    }

    const payload = {
      activeTaskId: currentTask?.id || null,
      activeTaskTitle: currentTask?.title || '无活跃任务',
      timeSpentMs: currentTask?.timeSpent || 0,
      isTracking: isTracking,
      mode: 'task',
      lastTick: Date.now(),
    };

    try {
      await fetch(`${this._bridgeUrl}/api/state`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Bridge-Token': this._authToken,
        },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      this._isOnline = false;
    }
  }

  private async _pollPendingActions(): Promise<void> {
    try {
      const res = await fetch(`${this._bridgeUrl}/api/action`, {
        method: 'GET',
        headers: {
          'X-Bridge-Token': this._authToken,
        },
      });
      if (res.ok) {
        const body = await res.json();
        if (body?.action?.action === 'toggle_tracking') {
          this._taskService.toggleStartTask();
        } else if (body?.action?.action === 'trigger_backup') {
          this.triggerBackup('mini_window_request');
        }
      }
    } catch {
      this._isOnline = false;
    }
  }

  async triggerBackup(source: string = 'manual'): Promise<boolean> {
    if (this._isBackingUp) {
      return false;
    }
    this._isBackingUp = true;

    try {
      const data =
        (await this._stateSnapshotService.getAllSyncModelDataFromStoreAsync()) as AppDataComplete;
      if (!hasMeaningfulStateData(data)) {
        Log.warn('LocalBridgeService: skipping backup — state is empty');
        return false;
      }

      const res = await fetch(`${this._bridgeUrl}/api/backup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Bridge-Token': this._authToken,
        },
        body: JSON.stringify(data),
      });

      if (res.ok) {
        const result = await res.json();
        Log.log(`LocalBridgeService: backup saved via ${source} -> ${result.filename}`);
        return true;
      }
    } catch (err) {
      Log.warn('LocalBridgeService: failed to write backup to local bridge', err);
    } finally {
      this._isBackingUp = false;
    }
    return false;
  }

  private async _sendBeaconBackup(): Promise<void> {
    if (!this._authToken || !this._isOnline) return;
    try {
      const data =
        (await this._stateSnapshotService.getAllSyncModelDataFromStoreAsync()) as AppDataComplete;
      if (hasMeaningfulStateData(data)) {
        const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
        navigator.sendBeacon(
          `${this._bridgeUrl}/api/backup?token=${encodeURIComponent(this._authToken)}`,
          blob,
        );
      }
    } catch {}
  }
}
