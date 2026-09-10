// chat-logic.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject } from 'rxjs';

import { SessionTimerService } from './session-timer.service';
import { InactivityService } from './inactivity.service';
import { TTSService } from './tts.service';
import { FeedbackService } from './feedback.service';
import { ChatSessionService, SessionState } from './chat-session.service';
import { IDLE_SECONDS, FINAL_SECONDS } from '../constants';          // ← umbrales únicos

@Injectable({ providedIn: 'root' })
export class ChatLogicService {
  private chatOpen = new BehaviorSubject<boolean>(false);
  chatState       = this.chatOpen.asObservable();

  public timerActive      = false;
  public inactivityActive = false;

  private chatDestroyed = false;

  constructor(
    public  timer: SessionTimerService,
    public  inactivity: InactivityService,
    public  tts: TTSService,
    public  feedback: FeedbackService,
    public  session: ChatSessionService,
    private http: HttpClient
  ) {
    this.monitorTimerAndInactivity();
  }

  /* ───────────────── interface para componentes ──────────────── */

  get isDestroyed(): boolean { return this.chatDestroyed; }

  resetChat(): void { this.chatDestroyed = false; }

  toggleChat(): void { this.chatOpen.next(!this.chatOpen.value); }

  closeChat(destroy = false): void {
    this.chatOpen.next(false);
    this.inactivity.stopWatch();
    this.timer.stop();
    this.tts.stop();

    if (destroy) {
      this.session.eliminarSesionDesdeBackend();
      this.chatDestroyed = true;
    }
  }

  /* ─────────────────────── restauración ──────────────────────── */

  restoreSessionState(): void {
    if (this.session.wasDeleted || this.chatDestroyed) return;

    const uuid            = this.session.storage.get<string>('session_uuid');
    const startedAtStr    = this.session.storage.get<string>('session_start');
    const lastActivityStr = localStorage.getItem('last_activity');
    if (!uuid || !startedAtStr) return;

    const startedAt = new Date(startedAtStr);
    if (isNaN(startedAt.getTime())) return;

    /* timer */
    this.timer.start(startedAt, d => this.session.updateSessionDuration(d));

    /* inactividad */
    if (lastActivityStr) {
      const lastActivity = +lastActivityStr;
      this.inactivity.restoreWatch(
        lastActivity,
        this.getInactivityCallbacks(),
        IDLE_SECONDS,
        FINAL_SECONDS
      );
    }

    /* mantén actualizado el observable de sesión */
    this.session.getSessionStateObservable().subscribe();
  }

  /* ─────────────────── inicio de nueva sesión ────────────────── */

  iniciarSession(onUpdate: (s: SessionState) => void): void {
    this.session.iniciar_session();

    const now = new Date();
    this.inactivity.updateActivity();                       // primer pulso
    this.timer.start(now, d => this.session.updateSessionDuration(d));

    this.iniciarInactividad();

    this.session.getSessionStateObservable().subscribe(state => {
      if (state) onUpdate(state);
    });
  }

  /* ─────────────────── inactividad / callbacks ───────────────── */

  private iniciarInactividad(): void {
    this.inactivity.startWatch(
      this.getInactivityCallbacks(),
      IDLE_SECONDS,
      FINAL_SECONDS
    );
  }

  private getInactivityCallbacks() {
    return {
      onInactivityStart : () => this.session.updateInactivity('', true),
      onInactivityEnd   : () => this.session.updateInactivity('', false),
      onAutoFinalize    : () => this.closeChat(true),
      onInactivityTick  : (s: number) => {
        const min = Math.floor(s / 60);
        const sec = s % 60;
        this.session.updateInactivity(`${min}m ${sec.toString().padStart(2, '0')}s`, true);
      },
      /* 🔄 vuelve a estar activo → ping al backend */
      onBecameActive    : () => this.session.keepAlive()
    };
  }

  /* ───────────────── monitor global de flags ─────────────────── */

  private monitorTimerAndInactivity(): void {
    this.timer.isActive$.subscribe(a => (this.timerActive = a));

    this.inactivity.isInactive$.subscribe(inactive => {
      this.inactivityActive = inactive;

      const state = this.session.getCurrentSession();
      if (state) {
        this.session.updateInactivity(state.inactivityDuration || '', inactive);
      }
    });
  }
}
