import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SessionStorageService {
  set<T>(key: string, value: T): void {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      console.error(`❌ Error guardando en sessionStorage[${key}]:`, e);
    }
  }

  get<T>(key: string): T | null {
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) as T : null;
    } catch (e) {
      console.error(`❌ Error leyendo de sessionStorage[${key}]:`, e);
      return null;
    }
  }

  remove(key: string): void {
    try {
      sessionStorage.removeItem(key);
    } catch (e) {
      console.error(`❌ Error eliminando sessionStorage[${key}]:`, e);
    }
  }

  clear(): void {
    try {
      sessionStorage.clear();
    } catch (e) {
      console.error(`❌ Error limpiando sessionStorage:`, e);
    }
  }

  has(key: string): boolean {
    return sessionStorage.getItem(key) !== null;
  }
}
