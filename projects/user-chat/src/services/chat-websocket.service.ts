import {Injectable} from '@angular/core';
import {Subject} from 'rxjs';
import {TTSService} from './tts.service';
import {environment} from '../environments/environment';

export interface ChatSocketMessage {
  type: string;
  data: any;
  /** Eco del identificador enviado con la pregunta. */
  request_id?: string;
}

@Injectable({providedIn: 'root'})
export class ChatWebSocketService {
  private socket?: WebSocket;
  private isConnected = false;

  private incoming$ = new Subject<ChatSocketMessage>();

  private readonly url = environment.chatSocketUrl;

  constructor(private tts: TTSService) {
  }

  /** Establece una única conexión persistente */
  connectSocket(): void {
    if (this.socket && this.isConnected) return;

    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.isConnected = true;
      console.log('🟢 WebSocket conectado');
    };

    this.socket.onmessage = (event) => {
      try {
        const msg: ChatSocketMessage = JSON.parse(event.data);

        if (msg.type === 'audio') {
          this.tts.playBase64Audio(msg.data);
        } else {
          this.incoming$.next(msg);
        }
      } catch (err) {
        console.error('❌ Error al parsear mensaje:', err);
      }
    };

    this.socket.onerror = (err) => {
      console.error('❌ WebSocket error:', err);
      this.incoming$.next({type: 'error', data: 'Error en WebSocket'});
      this.disconnect();
    };

    this.socket.onclose = () => {
      this.isConnected = false;
    };
  }

  /** Envía una nueva pregunta a través del socket */
  sendMessage(session_uuid: string, document_id: number, query: string, tts_enabled: boolean, request_id: string = ''): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn('⚠️ WebSocket no está conectado. Reintentando conexión...');
      this.connectSocket();
      setTimeout(() => {
        if (this.socket?.readyState === WebSocket.OPEN) {
          this.sendMessage(session_uuid, document_id, query, tts_enabled, request_id);
        }
      }, 500);
      return;
    }

    const payload = {
      session_uuid,
      document_id,
      query,
      tts_enabled,
      request_id
    };

    this.socket.send(JSON.stringify(payload));
  }

  /** Acceso al stream de mensajes */
  getMessages(): Subject<ChatSocketMessage> {
    return this.incoming$;
  }

  /** Cierra la conexión WebSocket */
  disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = undefined;
      this.isConnected = false;
    }
  }
}
