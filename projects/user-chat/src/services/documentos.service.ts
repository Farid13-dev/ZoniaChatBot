import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable, map, take} from 'rxjs';
import {environment} from '../environments/environment';
import {NgZone} from '@angular/core';

export interface Documento {
  id: number;
  nombre: string;
  descripcion: string;
  categoria: string;
}

export interface ChatMessage {
  sender: 'user' | 'bot';
  text: string;
  sources?: {
    indice: number;
    documento: string;
    pagina: string | number;
    url: string;
  }[];
  showSources?: boolean;
  documentSuggestions?: { [categoria: string]: Documento[] };
  subquestions?: string[];
  question_id?: number;
  answer_id?: number;
  feedback?: 'like' | 'dislike';
  streaming?: boolean;
  /** Identifica la pregunta que origino esta respuesta. Sirve para descartar
   *  mensajes que lleguen tarde de una pregunta anterior. */
  requestId?: string;
}

@Injectable({
  providedIn: 'root'
})
export class DocumentosService {
  constructor(private http: HttpClient, private ngZone: NgZone) {
  }

  listar(): Observable<Documento[]> {
    return this.http.get<Documento[]>(`${environment.apiBaseUrl}/list_documents`).pipe(take(1));
  }

  listarAgrupados(): Observable<{ [categoria: string]: Documento[] }> {
    return this.listar().pipe(
      map((docs: Documento[]) =>
        docs.reduce((acc, doc) => {
          if (!acc[doc.categoria]) acc[doc.categoria] = [];
          acc[doc.categoria].push(doc);
          return acc;
        }, {} as { [categoria: string]: Documento[] })
      )
    );
  }

  asociar(sessionUUID: string, documentoId: number): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}/asociar_documento`, {
      session_uuid: sessionUUID,
      document_id: documentoId
    }).pipe(take(1));
  }

  construirMensajeDeDocumentos(docs: Documento[]): ChatMessage {
    const mensajeDocs: ChatMessage = {
      sender: 'bot',
      text: '📄 Estos son los documentos disponibles para consultar:',
      documentSuggestions: {}
    };

    for (const doc of docs) {
      if (!mensajeDocs.documentSuggestions![doc.categoria]) {
        mensajeDocs.documentSuggestions![doc.categoria] = [];
      }

      mensajeDocs.documentSuggestions![doc.categoria].push({
        id: doc.id,
        nombre: doc.nombre,
        descripcion: doc.descripcion,
        categoria: doc.categoria
      });
    }

    return mensajeDocs;
  }


  construirDescripcionDocumento(doc: Documento): string {
    const rawDescripcion = doc.descripcion.split('—')[1]?.trim() ?? doc.descripcion;

    console.log('rawDescripcion: ', rawDescripcion);
    const descripcionLimpia = this.limpiarHtml(rawDescripcion);
    console.log('descripcionLimpia: ', descripcionLimpia);
    return `${descripcionLimpia}\n\n💬 ¡Puedes preguntarme lo que necesites sobre este documento!`;
  }

  // 👇 NUEVO: Simula escritura con efecto stream del saludo + documentos
  streamSaludoConDocumentos(
    messages: ChatMessage[],
    actualizarMensajes: () => void,
    onFinish: (mensajeDocs: ChatMessage) => void
  ): void {
    const bienvenida: ChatMessage = {
      sender: 'bot',
      text: ''
    };
    messages.push(bienvenida);
    actualizarMensajes();

    const texto = `👋 ¡Hola! Soy Zonia, tu asistente virtual experta sobre los estatutos de la Universidad de la Amazonia. Estoy aquí para ayudarte a resolver tus dudas y orientarte con base en los documentos oficiales disponibles.`;
    let i = 0;

    const interval = setInterval(() => {
      if (i < texto.length) {
        bienvenida.text += texto.charAt(i);
        actualizarMensajes();
        i++;
      } else {
        clearInterval(interval);
        this.listar().subscribe({
          next: (docs) => {
            const mensajeDocs = this.construirMensajeDeDocumentos(docs);
            onFinish(mensajeDocs);
          },
          error: (err) => {
            console.error('❌ Error cargando documentos:', err);
            alert('⚠️ No se pudieron cargar los documentos.');
          }
        });
      }
    }, 15);
  }

  // 👇 NUEVO: Simula escritura de descripción de un documento
  streamDescripcionDocumento(
    doc: Documento,
    messages: ChatMessage[],
    actualizarMensajes: () => void
  ): ChatMessage {
    const texto = this.construirDescripcionDocumento(doc);
    console.log('🧾 Texto a escribir:', texto);
    const mensaje: ChatMessage = {sender: 'bot', text: ''};
    messages.push(mensaje);
    actualizarMensajes();

    let i = 0;

    // 👇 Usa NgZone para que Angular detecte los cambios en el DOM
    this.ngZone.runOutsideAngular(() => {
      const interval = setInterval(() => {
        if (i < texto.length) {
          this.ngZone.run(() => {
            mensaje.text += texto.charAt(i);
            actualizarMensajes();
          });
          i++;
        } else {
          clearInterval(interval);
        }
      }, 15);
    });

    return mensaje;
  }

  private limpiarHtml(html: string): string {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;

    const lines: string[] = [];

    tmp.querySelectorAll('p, li, div, span').forEach(node => {
      const text = node.textContent?.trim();
      if (text) lines.push(text);
    });

    // Si no se extrajo nada, usa el texto completo
    if (lines.length === 0) {
      return tmp.textContent?.trim() ?? '';
    }

    return lines.join('\n');
  }


}
