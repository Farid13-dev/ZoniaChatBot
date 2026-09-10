// inactivity.service.ts
import { Injectable, NgZone } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { ChatSessionService } from './chat-session.service';
import { IDLE_SECONDS, FINAL_SECONDS } from '../constants';   // ← ruta según tu proyecto

export interface InactivityCallbacks {
  onInactivityStart: () => void;          // se alcanzó el umbral idle
  onInactivityEnd  : () => void;          // sigue activo pero todavía dentro de idleThreshold
  onAutoFinalize?  : () => void;          // alcanzó el tiempo de cierre
  onInactivityTick?: (seconds: number) => void;
  onBecameActive?  : () => void;          // vuelve a estar activo (para keep-alive)
}

@Injectable({ providedIn: 'root' })
export class InactivityService {
  private watcher: ReturnType<typeof setInterval> | null = null;
  private lastActivityTime = Date.now();

  private _inactive = new BehaviorSubject<boolean>(false);
  readonly isInactive$ = this._inactive.asObservable();

  constructor(private ngZone: NgZone, private chatSession: ChatSessionService) {
    /* 🔄 Sincronizar varias pestañas / ventanas */
    if (typeof window !== 'undefined') {
      window.addEventListener('storage', e => {
        if (e.key === 'last_activity' && e.newValue) {
          this.lastActivityTime = +e.newValue;
        }
      });
    }
  }

  /** Llamar en cada gesto del usuario y en cada chunk de respuesta */
  updateActivity(): void {
    this.lastActivityTime = Date.now();
    localStorage.setItem('last_activity', String(this.lastActivityTime));

    /* Si ya estaba marcado inactivo, cambia inmediatamente */
    if (this._inactive.value) this._inactive.next(false);
  }

  /** Inicia/ reinicia el watcher */
  startWatch(
    callbacks: InactivityCallbacks,
    idleThreshold: number = IDLE_SECONDS,
    finalizeThreshold: number = FINAL_SECONDS
  ): void {
    this.stopWatch();
    let inIdle = false;
    let idleSeconds = 0;

    this.ngZone.runOutsideAngular(() => {
      this.watcher = setInterval(() => {
        const secondsIdle = Math.floor((Date.now() - this.lastActivityTime) / 1000);

        /* 👉 entra en inactividad */
        if (!inIdle && secondsIdle >= idleThreshold) {
          inIdle = true;
          idleSeconds = 0;
          this.ngZone.run(() => {
            this._inactive.next(true);
            callbacks.onInactivityStart();
          });
        }

        /* 👉 mientras está inactivo */
        if (inIdle) {
          idleSeconds++;
          this.ngZone.run(() => callbacks.onInactivityTick?.(idleSeconds));

          if (idleSeconds >= finalizeThreshold) {
            this.ngZone.run(() => callbacks.onAutoFinalize?.());
          }
        }

        /* 👉 sale de inactividad */
        if (inIdle && secondsIdle < idleThreshold) {
          inIdle = false;
          idleSeconds = 0;
          this.ngZone.run(() => {
            this._inactive.next(false);
            callbacks.onInactivityEnd();
            callbacks.onBecameActive?.();           // keep-alive
          });
        }
      }, 1000);
    });
  }

  /** Restaura después de un reload */
  restoreWatch(
    lastActivityTimestamp: number,
    callbacks: InactivityCallbacks,
    idleThreshold: number = IDLE_SECONDS,
    finalizeThreshold: number = FINAL_SECONDS
  ): void {
    this.lastActivityTime = lastActivityTimestamp;
    this.startWatch(callbacks, idleThreshold, finalizeThreshold);

    /* Evaluación inmediata del estado actual */
    if ((Date.now() - lastActivityTimestamp) / 1000 >= idleThreshold) {
      this._inactive.next(true);
      callbacks.onInactivityStart();
    }
  }

  /** Detiene el watcher */
  stopWatch(): void {
    if (this.watcher) {
      clearInterval(this.watcher);
      this.watcher = null;
    }
    this._inactive.next(false);
  }
}
