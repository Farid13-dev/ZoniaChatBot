// chat.service.ts
import {Injectable} from '@angular/core';
import {BehaviorSubject, Observable} from 'rxjs';
import {HttpClient} from '@angular/common/http'; // Verifica que esté bien importado

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private chatOpen = new BehaviorSubject<boolean>(false);
  chatState = this.chatOpen.asObservable();
  messages: { content: string, sender: string }[] = [];

  private apiUrl = 'http://127.0.0.1:8000/predict-stream'; // Asegúrate de que la URL es correcta

  constructor(private http: HttpClient) {
  }

  toggleChat() {
    this.chatOpen.next(!this.chatOpen.value);
  }

  getMessages() {
    return this.messages;
  }

  sendMessageStream(content: string): Observable<string> {
    return new Observable<string>((observer) => {
      fetch(this.apiUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: content})
      }).then(async response => {
        const reader = response.body?.getReader();
        const decoder = new TextDecoder('utf-8');
        let previousText = "";  // Almacena el texto previo para evitar duplicaciones

        if (reader) {
          try {
            while (true) {
              const {done, value} = await reader.read();
              if (done) break;

              const chunk = decoder.decode(value, {stream: true});

              // Solo emite el texto nuevo que no sea duplicado
              if (chunk !== previousText) {
                observer.next(chunk);
                previousText = chunk;  // Actualiza el texto previo
              }
            }
            observer.complete();
          } catch (error) {
            observer.error(error);
          }
        } else {
          observer.error('El objeto reader no está disponible');
        }
      }).catch(error => observer.error(error));
    });
  }
}
