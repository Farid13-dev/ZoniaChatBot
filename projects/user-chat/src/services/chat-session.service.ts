// chat-session.service.ts
import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { BehaviorSubject, Observable } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { SessionStorageService } from './session-storage.service';
import { ChatMessage } from './documentos.service';

export interface SessionState {
  uuid: string;
  startedAt: Date;
  isActive: boolean;
  sessionDuration?: string;
  inactivityDuration?: string;
  inactive?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ChatSessionService {
  /* ----- claves de storage ----- */
  private readonly UUID_KEY     = 'session_uuid';
  private readonly START_KEY    = 'session_start';
  private readonly MESSAGES_KEY = 'chat_messages';
  private readonly DOCUMENT_KEY = 'selected_document';
  private readonly FEEDBACK_PREFIX = 'feedback_';

  /* ----- estado reactivo ----- */
  private sessionState$     = new BehaviorSubject<SessionState | null>(null);
  readonly  session$        = this.sessionState$.asObservable();

  private sessionDestroyed$ = new BehaviorSubject<boolean>(false);
  readonly  onSessionDestroyed$ = this.sessionDestroyed$.asObservable();

  private isBrowser: boolean;
  wasDeleted = false;

  constructor(
    @Inject(PLATFORM_ID) platformId: Object,
    private http: HttpClient,
    public  storage: SessionStorageService
  ) {
    this.isBrowser = isPlatformBrowser(platformId);
  }

  /* ────────────────────────────── ciclo de vida ───────────────────────────── */

  /** Arranca (o restaura) la sesión en la pestaña actual */
  initializeSessionLifecycle(): void {
    if (!this.isBrowser || this.wasDeleted) return;
    this.restoreSession();
  }

  getSessionStateObservable(): Observable<SessionState | null> {
    return this.session$;
  }
  getCurrentSession(): SessionState | null {
    return this.sessionState$.value;
  }

  /** Alta en el backend */
  iniciar_session(): void {
    if (!this.isBrowser) return;

    const uuid      = crypto.randomUUID();
    const startedAt = new Date();

    this.http.post('http://127.0.0.1:8000/init_session', { session_uuid: uuid })
      .subscribe({
        next : () => {
          this.persistSession(uuid, startedAt);
          this.wasDeleted = false;
          this.sessionState$.next({
            uuid, startedAt, isActive: true,
            sessionDuration: '00:00',
            inactivityDuration: '', inactive: false
          });
          this.sessionDestroyed$.next(false);
        },
        error: err => console.error('❌ Error creando sesión:', err)
      });
  }

  /** Cierre explícito desde el frontend */
  eliminarSesionDesdeBackend(): void {
    const session = this.getCurrentSession();
    if (!session?.uuid) return;

    this.wasDeleted = true;
    this.http.post('http://127.0.0.1:8000/end_session', { session_uuid: session.uuid })
      .subscribe({
        next : () => {
          console.log('✅ Sesión finalizada en backend');
          this.deleteSession();
        },
        error: err => {
          console.error('❌ Error al finalizar sesión:', err);
          this.deleteSession();
        }
      });
  }

  /** Mantiene viva la sesión (ping cada vez que el usuario vuelve a ser activo) */
  keepAlive(): void {
    const s = this.sessionState$.value;
    if (!s?.uuid) return;

    this.http.post('http://127.0.0.1:8000/keep_alive', { session_uuid: s.uuid })
      .subscribe({ error: e => console.error('keepAlive error:', e) });
  }

  /** Limpia todos los rastros locales de la sesión */
  deleteSession(): void {
    if (!this.isBrowser) return;

    this.storage.remove(this.UUID_KEY);
    this.storage.remove(this.START_KEY);
    this.storage.remove(this.MESSAGES_KEY);
    this.storage.remove(this.DOCUMENT_KEY);

    /* borra referencias para inactividad/timer */
    localStorage.removeItem('session_uuid');
    localStorage.removeItem('session_start');
    localStorage.removeItem('last_activity');

    const uuid = this.sessionState$.value?.uuid;
    if (uuid) this.clearAllFeedback(uuid);

    this.wasDeleted = true;
    this.sessionState$.next(null);
    this.sessionDestroyed$.next(true);
  }

  /* ──────────────────────────── restauración ─────────────────────────────── */

  private restoreSession(): void {
    const uuid         = this.storage.get<string>(this.UUID_KEY);
    const startedAtStr = this.storage.get<string>(this.START_KEY);

    if (uuid && startedAtStr) {
      this.http.get<{ exists: boolean }>(
        `http://127.0.0.1:8000/estado_sesion?session_uuid=${uuid}`
      ).subscribe({
        next : res => {
          if (res.exists) {
            const startedAt = new Date(startedAtStr);
            this.sessionState$.next({ uuid, startedAt, isActive: true });
          } else {
            this.deleteSession();
          }
        },
        error: () => this.deleteSession()
      });
    }
  }

  private persistSession(uuid: string, startedAt: Date): void {
    this.storage.set(this.UUID_KEY, uuid);
    this.storage.set(this.START_KEY, startedAt.toISOString());
  }

  /* ────────────────────────────── updates UI ─────────────────────────────── */

  updateSessionDuration(duration: string): void {
    const cur = this.sessionState$.value;
    if (cur?.uuid) this.sessionState$.next({ ...cur, sessionDuration: duration });
  }

  updateInactivity(duration: string, inactive: boolean): void {
    const cur = this.sessionState$.value;
    if (cur?.uuid) this.sessionState$.next({ ...cur, inactivityDuration: duration, inactive });
  }

  /* ──────────────────────────── persistencia chat ────────────────────────── */

  saveMessages(messages: ChatMessage[]): void {
    this.storage.set(this.MESSAGES_KEY, messages);
  }
  getMessages(): ChatMessage[] {
    return this.storage.get<ChatMessage[]>(this.MESSAGES_KEY) || [];
  }

  /* documento asociado */
  setSelectedDocument(id: number | null): void {
    if (id === null) this.storage.remove(this.DOCUMENT_KEY);
    else this.storage.set(this.DOCUMENT_KEY, id);
  }
  getSelectedDocument(): number | null {
    return this.storage.get<number>(this.DOCUMENT_KEY);
  }

  /* feedback (localStorage) */
  saveFeedback(sessionId: string, q: number, a: number, val: 'like' | 'dislike'): void {
    localStorage.setItem(`${this.FEEDBACK_PREFIX}${sessionId}_${q}_${a}`, val);
  }
  getFeedback(sessionId: string, q: number, a: number): 'like' | 'dislike' | null {
    return localStorage.getItem(
      `${this.FEEDBACK_PREFIX}${sessionId}_${q}_${a}`
    ) as 'like' | 'dislike' | null;
  }
  clearAllFeedback(sessionId: string): void {
    Object.keys(localStorage).forEach(k => {
      if (k.startsWith(`${this.FEEDBACK_PREFIX}${sessionId}_`)) {
        localStorage.removeItem(k);
      }
    });
  }
}
