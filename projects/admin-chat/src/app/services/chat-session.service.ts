import {Injectable} from '@angular/core';

@Injectable({providedIn: 'root'})
export class ChatSessionService {
  private readonly UUID_KEY = 'session_uuid';
  private readonly MESSAGES_KEY = 'chat_messages';
  private readonly START_KEY = 'session_started_at';

  getSessionUUID(): string {
    let uuid = localStorage.getItem(this.UUID_KEY);
    if (!uuid) {
      uuid = crypto.randomUUID();
      localStorage.setItem(this.UUID_KEY, uuid);
    }
    return uuid;
  }

  resetSessionUUID() {
    localStorage.removeItem(this.UUID_KEY);
  }

  saveMessages(messages: any[]) {
    sessionStorage.setItem(this.MESSAGES_KEY, JSON.stringify(messages));
  }

  getMessages(): any[] {
    const stored = sessionStorage.getItem(this.MESSAGES_KEY);
    return stored ? JSON.parse(stored) : [];
  }

  clearMessages() {
    sessionStorage.removeItem(this.MESSAGES_KEY);
  }

  setSessionStartTime(date: Date) {
    sessionStorage.setItem(this.START_KEY, date.toISOString());
  }

  getSessionStartTime(): Date | null {
    const stored = sessionStorage.getItem(this.START_KEY);
    return stored ? new Date(stored) : null;
  }

  clearSessionStartTime() {
    sessionStorage.removeItem(this.START_KEY);
  }

  clearAll() {
    this.clearMessages();
    this.clearSessionStartTime();
    this.resetSessionUUID();
  }

}
