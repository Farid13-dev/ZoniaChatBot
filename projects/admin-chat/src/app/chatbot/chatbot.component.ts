import {
  ViewChild,
  ElementRef,
  ApplicationRef,
  Component,
  OnInit,
  OnDestroy,
  AfterViewInit,
  ChangeDetectorRef, HostListener,
  ChangeDetectionStrategy
} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {ChatSessionService} from '../services/chat-session.service';
import {NgZone} from '@angular/core';
import {take} from 'rxjs/operators';
import {environment} from '../../environments/environment';

interface ChatMessage {
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
  // 👉 Añade esta línea:
  feedback?: 'like' | 'dislike';
}

interface Documento {
  id: number;
  nombre: string;
  categoria: string;
}

@Component({
    selector: 'app-chatbot',
    imports: [CommonModule, FormsModule],
    templateUrl: './chatbot.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./chatbot.component.css']
})
//estado del chat
export class ChatbotComponent implements AfterViewInit, OnInit, OnDestroy {
  messages: ChatMessage[] = [];
  messageInput = '';
  processing = false;

  //session
  sessionUUID: string = '';
  sessionStartedAt: Date | null = null;
  sessionDuration = '00:00';
  sessionFinalizada = false;
  sessionCerrada = false;

  //inactividad
  lastActivityTime = Date.now();
  inactive = false;
  inactivityDuration: string = '';
  private timerInterval: any;
  inactivityWatcher: any;

  //Documentos
  documentoSeleccionado = false;
  documentoSeleccionadoId: number | null = null;

  //Audio y TTS
  audioContext = new AudioContext();
  audioQueue: AudioBuffer[] = [];
  isPlaying = false;
  private currentAudioSource: AudioBufferSourceNode | null = null;

  //Opciones UI
  isTTSActive: boolean = true;
  isOCRActive = true;
  isASRActive = true;
  isOptionsMenuVisible = false;
// Opciones UI
  generateSubquestions: boolean = true;  // 👈 NUEVO: permite controlar desde la UI
  private featureFlagSocket: WebSocket | null = null;

  @ViewChild('chatContainer') chatContainer!: ElementRef<HTMLDivElement>;


  constructor(private http: HttpClient,
              private chatSession: ChatSessionService,
              private ngZone: NgZone,
              private appRef: ApplicationRef,
              private cdr: ChangeDetectorRef,
  ) {
  }

  //Ciclo de vida
  ngOnInit() {
    this.appRef.isStable.subscribe((stable: boolean) => {
      console.log('[Hydration Debug] isStable:', stable);
    });

    this.sessionUUID = this.chatSession.getSessionUUID();
    this.messages = this.chatSession.getMessages();
    this.sessionStartedAt = this.chatSession.getSessionStartTime();

    if (!this.sessionStartedAt) {
      this.sessionStartedAt = new Date();
      this.chatSession.setSessionStartTime(this.sessionStartedAt);
      this.checkASRStatus();
      this.fetchOCRStatus();
      this.iniciarFeatureFlagSocket();
      this.verificarEstadoSesion();

    }

    setTimeout(() => {
      this.startSessionTimer();
      this.startInactivityWatcher();
    }, 0);

    // Restaurar feedback en mensajes del chat si existen votos guardados
    this.messages.forEach((msg) => {
      if (msg.sender === 'bot' && msg.question_id && msg.answer_id) {
        const savedFeedback = this.getFeedbackState(msg.question_id, msg.answer_id);
        if (savedFeedback) {
          msg.feedback = savedFeedback;
        }
      }
    });

    // ✅ Detectar sesión cerrada tras recarga
    if (!localStorage.getItem('session_uuid') && !sessionStorage.getItem('session_uuid')) {
      this.sessionCerrada = true;
    }

    const storedTTS = localStorage.getItem('tts_active');
    const storedSUB = localStorage.getItem('subq_active');

    this.isTTSActive = storedTTS !== null ? JSON.parse(storedTTS) : true;
    this.generateSubquestions = storedSUB !== null ? JSON.parse(storedSUB) : true;
  }


  ngAfterViewInit() {
    // Verificar visibilidad del botón de scroll al inicio
    this.checkASRStatus();
    this.fetchOCRStatus();
  }


  ngOnDestroy() {
    if (this.timerInterval) clearInterval(this.timerInterval);  // ✅ LIMPIEZA DE TIMERS AL DESTRUIR EL COMPONENTE
    if (this.inactivityWatcher) clearInterval(this.inactivityWatcher);
    if (this.featureFlagSocket) {
      this.featureFlagSocket.close();
      this.featureFlagSocket = null;
    }

  }

  //control sesion
  generateSessionUUID(): string {
    return crypto.randomUUID();
  }

  iniciar_session() {
    this.sessionUUID = this.generateSessionUUID();
    localStorage.setItem('session_uuid', this.sessionUUID);
    this.initSession();
    this.startInactivityWatcher();

  }

  initSession() {
    this.sessionFinalizada = false;
    this.inactive = false;
    this.messages = [];
    this.sessionDuration = '';
    this.inactivityDuration = '';
    this.lastActivityTime = Date.now();

    this.http.post<any>('http://127.0.0.1:8000/init_session', {
      session_uuid: this.sessionUUID
    }).pipe(take(1)).subscribe({
      next: (res) => {
        this.sessionStartedAt = new Date(res.started_at);
        this.startSessionTimer();
        this.startInactivityWatcher();


        if (this.messages.length === 0) {
          this.listarDocumentosDisponibles(true);
        }
      },
      error: (err) => {
        console.error('Error iniciando sesión:', err);
        alert('❌ Error iniciando sesión');
      }
    });

  }

  stopSession() {
    clearInterval(this.timerInterval);
    clearInterval(this.inactivityWatcher);
    this.sessionUUID = '';
    this.sessionStartedAt = null;
    this.sessionDuration = '';
    this.sessionFinalizada = true;
    this.inactive = false;
    this.messages = [];
    this.clearAllFeedbackVotes();
    this.chatSession.clearAll();
  }

  resetSession() {
    this.stopSession();
    this.sessionUUID = this.generateSessionUUID();
    localStorage.setItem('session_uuid', this.sessionUUID);
    this.initSession();
    this.startInactivityWatcher();
  }

  deleteSession() {
    if (!this.sessionUUID) return;
    if (confirm('¿Seguro que quieres eliminar la sesión actual?')) {
      this.http.post('http://127.0.0.1:8000/end_session', {
        session_uuid: this.sessionUUID
      }).pipe(take(1)).subscribe({
        next: () => {
          this.stopSession();
          alert('✅ Sesión eliminada correctamente.');
        },
        error: (err) => {
          console.error('❌ Error al eliminar sesión:', err);
          alert('⚠️ No se pudo eliminar la sesión.');
        }
      });
    }
  }

  verificarEstadoSesion() {
    if (!this.sessionUUID) return;
    this.http.get<any>(`http://127.0.0.1:8000/estado_sesion?session_uuid=${this.sessionUUID}`).pipe(take(1)).subscribe({
      next: (res) => {
        if (res.exists && res.documento_seleccionado) {
          this.documentoSeleccionado = true;
          this.documentoSeleccionadoId = res.document_id;
        }
      },
      error: (err) => {
        console.error('❌ Error al verificar el estado de la sesión:', err);
      }
    });
  }

  //inactividad
  // TIMER DE SESIÓN CON run() PARA CAMBIOS
  startSessionTimer() {
    if (this.timerInterval) clearInterval(this.timerInterval);
    this.sessionStartedAt = new Date();

    this.ngZone.runOutsideAngular(() => {
      this.timerInterval = setInterval(() => {
        const now = new Date();
        const diff = now.getTime() - this.sessionStartedAt!.getTime();
        const minutes = Math.floor(diff / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);
        const durationFormatted = `${minutes}m ${seconds < 10 ? '0' : ''}${seconds}s`;

        this.ngZone.run(() => {
          this.sessionDuration = durationFormatted;
        });
      }, 1000);
    });
  }

  // TIMER DE INACTIVIDAD CON run() PARA VISTA
  startInactivityWatcher() {
    if (this.inactivityWatcher) clearInterval(this.inactivityWatcher);

    let inactividadDetectada = false;
    let segundosDesdeInactividad = 0;

    this.ngZone.runOutsideAngular(() => {
      this.inactivityWatcher = setInterval(() => {
        const now = Date.now();
        const segundosInactivos = Math.floor((now - this.lastActivityTime) / 1000);

        if (!inactividadDetectada && segundosInactivos >= 15) {
          inactividadDetectada = true;
          segundosDesdeInactividad = 0;
          this.ngZone.run(() => this.inactive = true);
        }

        if (inactividadDetectada) {
          segundosDesdeInactividad++;
          const min = Math.floor(segundosDesdeInactividad / 60);
          const sec = segundosDesdeInactividad % 60;
          this.ngZone.run(() => {
            this.inactivityDuration = `${min}m ${sec < 60 ? '0' : ''}${sec}s`;
          });

          if (segundosDesdeInactividad >= 600 && !this.sessionFinalizada) {
            this.ngZone.run(() => this.finalizeSessionForInactivity());
          }
        }

        if (segundosInactivos < 15) {
          inactividadDetectada = false;
          segundosDesdeInactividad = 0;
          this.ngZone.run(() => {
            this.inactive = false;
            this.inactivityDuration = '';
          });
        }
      }, 1000);
    });
  }

  updateActivity() {
    this.lastActivityTime = Date.now();
    this.inactive = false;
  }

  finalizeSessionForInactivity() {
    this.sessionFinalizada = true;
    this.http.post('http://127.0.0.1:8000/end_session', {
      session_uuid: this.sessionUUID
    }).pipe(take(1)).subscribe({
      next: () => {
        alert('⚠️ Tu sesión ha finalizado por inactividad.');
        this.stopSession();
      },
      error: (err) => {
        console.error('❌ Error finalizando sesión:', err);
        this.stopSession();
      }
    });
  }

  //gestion de documentos
  listarDocumentosDisponibles(mostrarSaludo = true) {
    // Elimina sugerencias previas si existen
    this.messages = this.messages.filter(m => !m.documentSuggestions);
    this.actualizarMensajes();

    if (mostrarSaludo) {
      const bienvenida: ChatMessage = {
        sender: 'bot',
        text: ''
      };
      this.messages.push(bienvenida);
      this.actualizarMensajes();

      const textoBienvenida = `👋 ¡Hola! Soy Zonia, tu asistente virtual experta sobre los estatutos de la Universidad de la Amazonia. Estoy aquí para ayudarte a resolver tus dudas y orientarte con base en los documentos oficiales disponibles.`;
      let i = 0;

      const streamBienvenida = setInterval(() => {
        if (i < textoBienvenida.length) {
          bienvenida.text += textoBienvenida.charAt(i);
          this.actualizarMensajes();
          i++;
        } else {
          clearInterval(streamBienvenida);
          this.mostrarDocumentosFade(); // Mostrar documentos al terminar
        }
      }, 15);
    } else {
      // Si no hay saludo, mostrar directamente los documentos
      this.mostrarDocumentosFade();
    }
  }

  mostrarDocumentosFade() {
    this.http.get<any[]>('http://127.0.0.1:8000/list_documents').pipe(take(1)).subscribe({
      next: (docs) => {
        const mensajeDocs: ChatMessage = {
          sender: 'bot',
          text: '📄 ¡Estos son los documentos disponibles para consultar!',
          documentSuggestions: {}
        };

        for (const doc of docs) {
          if (!mensajeDocs.documentSuggestions![doc.categoria]) {
            mensajeDocs.documentSuggestions![doc.categoria] = [];
          }

          mensajeDocs.documentSuggestions![doc.categoria].push({
            id: doc.id,
            nombre: `${doc.nombre} — ${doc.descripcion}`,
            categoria: doc.categoria
          });
        }

        // Esperar doble ciclo de renderizado para asegurar que chatContainer y DOM estén listos
        setTimeout(() => {
          this.messages.push(mensajeDocs);
          this.actualizarMensajes();

          // Segundo ciclo para asegurar el scroll
          setTimeout(() => this.scrollToBottom(), 100);
        }, 100);
      },
      error: (err) => {
        console.error('❌ Error obteniendo documentos:', err);
        alert('⚠️ No se pudieron obtener los documentos disponibles.');
      }
    });
  }

  seleccionarDocumento(doc: Documento) {
    this.documentoSeleccionado = true;
    this.documentoSeleccionadoId = doc.id;

    // Elimina mensaje con documentos
    this.messages = this.messages.filter(m => !m.documentSuggestions);

    const mensajeStream: ChatMessage = {
      sender: 'bot',
      text: ''
    };
    this.messages.push(mensajeStream);
    this.actualizarMensajes();

    const rawDescripcion = doc.nombre.split('—')[1]?.trim() ?? doc.nombre;
    const descripcionLimpia = this.limpiarHtml(rawDescripcion);
    const textoFinal = ` ${rawDescripcion}\n\n💬 Puedes preguntarme lo que necesites sobre este documento.`;
    let index = 0;

    const intervalo = setInterval(() => {
      if (index < textoFinal.length) {
        mensajeStream.text += textoFinal.charAt(index);
        this.actualizarMensajes();
        index++;
      } else {
        clearInterval(intervalo);
      }
    }, 15);

    this.http.post('http://127.0.0.1:8000/asociar_documento', {
      session_uuid: this.sessionUUID,
      document_id: doc.id
    }).pipe(take(1)).subscribe({
      next: () => console.log(`✅ Documento ${doc.id} asociado`),
      error: (err) => {
        console.error('❌ Error al asociar documento:', err);
        alert('⚠️ No se pudo asociar el documento.');
      }
    });
  }

  volverAVerDocumentos() {
    this.documentoSeleccionado = false;
    this.documentoSeleccionadoId = null;

    // Limpia subpreguntas
    this.messages = this.messages.map(msg =>
      msg.subquestions ? {...msg, subquestions: []} : msg
    );

    // Reutiliza listarDocumentosDisponibles sin saludo
    this.listarDocumentosDisponibles(false);
  }

  // Chat y WebSocket
  mostrarBotonVolverADocumentosConSubpreguntas(message: ChatMessage): boolean {
    return this.documentoSeleccionado &&
      this.documentoSeleccionadoId !== null &&
      Array.isArray(message.subquestions) &&
      message.subquestions.length > 0;
  }


  enviarPreguntaStream(mensajeUsuario: string, documentoId: number) {
    this.stopCurrentTTS();
    this.updateActivity();
    this.processing = true;

    const pregunta: ChatMessage = {
      sender: 'user',
      text: mensajeUsuario
    };
    this.messages.push(pregunta);
    this.messages = this.messages.map(m => {
      if (m.subquestions) {
        return {...m, subquestions: []};
      }
      return m;
    });

    const respuesta: ChatMessage = {
      sender: 'bot',
      text: '',
      showSources: false,
      sources: [],
      subquestions: []
    };
    this.messages.push(respuesta);
    this.actualizarMensajes();

    const socket = new WebSocket('ws://127.0.0.1:8000/ws/chat');

    socket.onopen = () => {
      socket.send(JSON.stringify({
        session_uuid: this.sessionUUID,
        document_id: documentoId,
        query: mensajeUsuario,
        tts_enabled: this.isTTSActive,
        generate_subquestions: this.generateSubquestions
      }));
    };


    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === 'chunk') {
        respuesta.text += msg.data;
      } else if (msg.type === 'audio') {
        this.playBase64Audio(msg.data);
      } else if (msg.type === 'metadata') {
        respuesta.sources = msg.data.sources || [];
        respuesta.subquestions = msg.data.subquestions || [];
        respuesta.showSources = true;
      } else if (msg.type === 'end') {
        this.processing = false;
      } else if (msg.type === 'error') {
        respuesta.text += `\n⚠️ Error: ${msg.data}`;
        this.processing = false;
      } else if (msg.type === 'response_ids') {
        (respuesta as any).question_id = msg.data.question_id;
        (respuesta as any).answer_id = msg.data.answer_id;

// Recuperar voto si existe en localStorage
        const savedFeedback = this.getFeedbackState(msg.data.question_id, msg.data.answer_id);
        if (savedFeedback) {
          (respuesta as any).feedback = savedFeedback;
        }

      }

      this.actualizarMensajes();
    };

    socket.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
      respuesta.text += '\n⚠️ Error en la conexión WebSocket.';
      this.processing = false;
      this.actualizarMensajes();
      socket.close();
    };

    socket.onclose = () => {
      this.processing = false;
    };
  }


  handleUserInput() {
    const pregunta = this.messageInput.trim();
    if (pregunta && !this.processing && this.documentoSeleccionado && this.documentoSeleccionadoId !== null) {
      this.enviarPreguntaStream(pregunta, this.documentoSeleccionadoId);
      this.messageInput = '';
    }
  }

  // Audio y TTS
  playBase64Audio(base64: string) {
    if (!this.isTTSActive) return;

    const binary = atob(base64);
    const buffer = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      buffer[i] = binary.charCodeAt(i);
    }

    this.audioContext.decodeAudioData(buffer.buffer, (decoded) => {
      this.audioQueue.push(decoded);     // 👈 Añadir a la cola
      this.playNextInQueue();           // 👈 Intentar reproducir
    }, (error) => {
      console.error("🎧 Error decoding audio:", error);
    });
  }


  playNextInQueue() {
    if (this.isPlaying || this.audioQueue.length === 0) return;

    const nextBuffer = this.audioQueue.shift();
    if (!nextBuffer) return;

    const source = this.audioContext.createBufferSource();
    source.buffer = nextBuffer;
    source.connect(this.audioContext.destination);
    source.onended = () => {
      this.isPlaying = false;
      this.playNextInQueue();  // 👈 continúa con el siguiente audio
    };

    this.isPlaying = true;
    source.start(0);
  }

  stopCurrentTTS() {
    if (this.currentAudioSource) {
      this.currentAudioSource.stop();
      this.currentAudioSource.disconnect();
      this.currentAudioSource = null;
    }
    this.isPlaying = false;
    this.audioQueue = []; // ⚠️ Vacía la cola
  }

  //Feedback
  likeAnswer(questionId: number, answerId: number, message: any) {
    if (message.feedback) return;

    const payload = {
      session_uuid: this.sessionUUID,
      question_id: questionId,
      answer_id: answerId
    };

    this.http.post('http://127.0.0.1:8000/like_answer', payload).pipe(take(1)).subscribe({
      next: () => {
        message.feedback = 'like';
        this.saveFeedbackState(questionId, answerId, 'like');
      },
      error: () => alert('⚠️ Error al registrar like')
    });
  }

  dislikeAnswer(questionId: number, answerId: number, message: any) {
    if (message.feedback) return;

    const payload = {
      session_uuid: this.sessionUUID,
      question_id: questionId,
      answer_id: answerId
    };

    this.http.post('http://127.0.0.1:8000/dislike_answer', payload).pipe(take(1)).subscribe({
      next: () => {
        message.feedback = 'dislike';
        this.saveFeedbackState(questionId, answerId, 'dislike');
      },
      error: () => alert('⚠️ Error al registrar dislike')
    });
  }

  saveFeedbackState(questionId: number, answerId: number, value: 'like' | 'dislike') {
    const key = `feedback_${this.sessionUUID}_${questionId}_${answerId}`;
    localStorage.setItem(key, value);
  }


  getFeedbackState(questionId: number, answerId: number): 'like' | 'dislike' | null {
    const key = `feedback_${this.sessionUUID}_${questionId}_${answerId}`;
    return localStorage.getItem(key) as 'like' | 'dislike' | null;
  }

  clearAllFeedbackVotes() {
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith(`feedback_${this.sessionUUID}_`)) {
        localStorage.removeItem(key);
      }
    });
  }

  // Utilidades
  actualizarMensajes() {
    sessionStorage.setItem('chat_messages', JSON.stringify(this.messages));
    this.scrollToBottom(); // 👈 desplazarse al fondo
  }

  limpiarHtml(html: string): string {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;

    // Remueve saltos vacíos y conserva estructura
    const lines: string[] = [];
    tmp.querySelectorAll('p, li, div').forEach(node => {
      const text = node.textContent?.trim();
      if (text) lines.push(text);
    });

    return lines.join('\n');
  }

  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }

  scrollToBottom() {
    setTimeout(() => {
      this.chatContainer?.nativeElement.scrollTo({
        top: this.chatContainer.nativeElement.scrollHeight,
        behavior: 'smooth'
      });
    }, 50);
  }


  //Menú de opciones: ASR / TTS / OCR / Calificación
  toggleOptionsMenu() {
    this.isOptionsMenuVisible = !this.isOptionsMenuVisible;
  }

  toggleASR() {
    this.isASRActive = !this.isASRActive;

    const body = {
      state: this.isASRActive,
      token: environment.adminToken // ✅ Leído desde environment.ts
    };

    this.http.post('http://127.0.0.1:8001/toggle-asr', body).subscribe({
      next: (res) => {
        console.log('✅ Estado ASR actualizado:', res);
      },
      error: (err) => {
        console.error('❌ Error al cambiar ASR:', err);
        this.isASRActive = !this.isASRActive; // Revertimos visualmente si falló
      }
    });

    this.isOptionsMenuVisible = false;
  }

  checkASRStatus() {
    this.http.get<{ asr_active: boolean }>('http://127.0.0.1:8001/asr-status').subscribe({
      next: (res) => {
        this.isASRActive = res.asr_active;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.warn('No se pudo obtener el estado del ASR', err);
        this.isASRActive = false;
        this.cdr.markForCheck();
      }
    });
  }


  toggleOCR() {
    this.isOCRActive = !this.isOCRActive;
    const params = {
      state: this.isOCRActive,
      token: environment.adminToken
    };

    this.http.post('http://127.0.0.1:8002/toggle-ocr', params).subscribe({
      next: (res) => {
        console.log('✅ Estado OCR actualizado:', res);
      },
      error: (err) => {
        console.error('❌ Error al cambiar OCR:', err);
        this.isOCRActive = !this.isOCRActive;
      }
    });


    this.isOptionsMenuVisible = false;
  }

  fetchOCRStatus() {
    this.http.get<{ ocr_active: boolean }>('http://127.0.0.1:8002/ocr-status').subscribe({
      next: (res) => {
        this.isOCRActive = res.ocr_active;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('❌ No se pudo obtener el estado OCR:', err);
        this.isOCRActive = false; // Por seguridad, desactívalo si falla
        this.cdr.markForCheck();
      }
    });
  }

  toggleTTS() {
    this.isTTSActive = !this.isTTSActive;
    console.log("🔈 TTS ahora está:", this.isTTSActive ? "Activado" : "Desactivado");

    if (!this.isTTSActive) {
      this.stopCurrentTTS();  // Detiene el audio actual si está sonando
    }
  }

  toggleSUB() {
    this.generateSubquestions = !this.generateSubquestions;
    console.log("🔈 Sub ahora está:", this.generateSubquestions ? "Activado" : "Desactivado");
  }

  toggleGlobalTTS() {
    this.isTTSActive = !this.isTTSActive;

    this.http.post('http://127.0.0.1:8000/toggle', {
      key: 'tts_active',
      state: this.isTTSActive,
      token: environment.adminToken
    }).subscribe({
      next: () => {
        console.log('✅ TTS global actualizado');
        localStorage.setItem('tts_active', JSON.stringify(this.isTTSActive));
      },
      error: () => {
        alert('❌ Error al cambiar el estado global de TTS');
        this.isTTSActive = !this.isTTSActive;
      }
    });
  }

  toggleGlobalSUB() {
    this.generateSubquestions = !this.generateSubquestions;

    this.http.post('http://127.0.0.1:8000/toggle', {
      key: 'subq_active',
      state: this.generateSubquestions,
      token: environment.adminToken
    }).subscribe({
      next: () => {
        console.log('✅ Subpreguntas global actualizado');
        localStorage.setItem('subq_active', JSON.stringify(this.generateSubquestions));
      },
      error: () => {
        alert('❌ Error al cambiar el estado global de subpreguntas');
        this.generateSubquestions = !this.generateSubquestions;
      }
    });
  }


  iniciarFeatureFlagSocket() {
  // Paso 1: consulta el estado inicial
  this.http.get<any>('http://127.0.0.1:8000/status').subscribe({
    next: (flags) => {
      if (typeof flags.tts_active === 'boolean') {
        this.isTTSActive = flags.tts_active;
        localStorage.setItem('tts_active', JSON.stringify(this.isTTSActive));
      }
      if (typeof flags.subq_active === 'boolean') {
        this.generateSubquestions = flags.subq_active;
        localStorage.setItem('subq_active', JSON.stringify(this.generateSubquestions));
      }
      this.cdr.markForCheck();
    },
    error: (err) => {
      console.warn("❌ No se pudo obtener estado inicial de feature flags:", err);
    }
  });

  // Paso 2: conecta el WebSocket para futuras actualizaciones
  this.featureFlagSocket = new WebSocket('ws://127.0.0.1:8000/ws/feature_flags');

  this.featureFlagSocket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.event === 'flag_changed') {
      if (msg.key === 'tts_active') {
        this.isTTSActive = msg.state;
        localStorage.setItem('tts_active', JSON.stringify(msg.state));
        if (!msg.state) this.stopCurrentTTS();
      }
      if (msg.key === 'subq_active') {
        this.generateSubquestions = msg.state;
        localStorage.setItem('subq_active', JSON.stringify(msg.state));
      }

      this.cdr.markForCheck();
    }
  };

  this.featureFlagSocket.onerror = (e) => {
    console.warn("⚠️ WebSocket de flags desconectado", e);
    this.featureFlagSocket = null;
  };

  this.featureFlagSocket.onclose = () => {
    this.featureFlagSocket = null;
  };
}


  //Evento global
  @HostListener('document:click', ['$event'])
  onClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.options-menu') && !target.closest('.btn-toggle-admin')) {
      this.isOptionsMenuVisible = false;
    }
  }
}
