import {
  Component, ViewChild, ElementRef, AfterViewInit, ChangeDetectorRef,
  NgZone, HostListener, Inject, PLATFORM_ID, OnInit, OnDestroy,
  ChangeDetectionStrategy
} from '@angular/core';
import { isPlatformBrowser, CommonModule, NgClass } from '@angular/common';
import {ChatMessagesComponent} from '../chat-messages/chat-messages.component';
import {ChatInputComponent} from '../chat-input/chat-input.component';
import {
  ChatSessionService, SessionState
} from '../../services/chat-session.service';
import {ChatLogicService} from '../../services/chat-logic.service';
import {DocumentosService, Documento, ChatMessage} from '../../services/documentos.service';
import {ChatSocketMessage, ChatWebSocketService} from '../../services/chat-websocket.service';
import {FeedbackService} from '../../services/feedback.service';
import {Subscription} from 'rxjs';
import {HttpClient} from "@angular/common/http";
import {TTSService} from "../../services/tts.service";

@Component({
    selector: 'app-chat-modal',
    templateUrl: './chat-modal.component.html',
    styleUrls: ['./chat-modal.component.css'],
    changeDetection: ChangeDetectionStrategy.Eager,
    imports: [
    CommonModule,
    ChatMessagesComponent,
    ChatInputComponent,
    NgClass
]
})
export class ChatModalComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('chatDisplay', {static: true}) chatDisplay!: ElementRef;
  @ViewChild(ChatInputComponent) chatInputComponent!: ChatInputComponent;

  isASRActive = true;
  isOCRActive = true;
  isSendActive = false;
  isTTSActive = true;
  generateSubquestions = true;

  isOpen = false;
  isOptionsMenuVisible = false;
  showScrollToBottomButton = false;
  private shouldScrollToBottom = false;

  private ocrSocket?: WebSocket;
  private isDestroyed = false;
  private asrSocket?: WebSocket;

  messages: ChatMessage[] = [];
  documentoSeleccionadoId: number | null = null;
  sessionState: SessionState | null = null;
  haMostradoDocumentos = false;

  private sessionSubscription?: Subscription;
  private sessionDestroySub?: Subscription;
  private wsSubscription?: Subscription;

  private respuestaActual?: ChatMessage;

  constructor(
    private http: HttpClient,
    private session: ChatSessionService,
    protected chatLogic: ChatLogicService,
    private documentosService: DocumentosService,
    private ws: ChatWebSocketService,
    private feedback: FeedbackService,
    private cdr: ChangeDetectorRef,
    private ngZone: NgZone,
    private tts: TTSService,
    @Inject(PLATFORM_ID) private platformId: Object,
  ) {
    this.chatLogic.chatState.subscribe(open => {
      this.ngZone.run(() => {
        this.isOpen = open;
      });
    });
  }

  ngOnInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    this.session.initializeSessionLifecycle();
    this.chatLogic.restoreSessionState();

    this.messages = this.session.getMessages();
    this.shouldScrollToBottom = true;
    this.documentoSeleccionadoId = this.session.getSelectedDocument();

    this.sessionSubscription = this.session.getSessionStateObservable().subscribe(state => {
      const nuevaSesion = state?.uuid !== this.sessionState?.uuid;
      this.sessionState = state;
      this.cdr.markForCheck();

      // ✅ Restaurar feedback si ya hay sesión válida
      if (state?.uuid) {
        this.messages.forEach(msg => {
          if (msg.question_id && msg.answer_id) {
            const storedFeedback = this.feedback.getFeedback(
              state.uuid,
              msg.question_id,
              msg.answer_id
            );
            if (storedFeedback) msg.feedback = storedFeedback;
          }
        });
      }

      if (nuevaSesion && state?.uuid && state.isActive && !this.documentoSeleccionadoId) {
        this.resetUI();
        this.haMostradoDocumentos = true;
        this.listarDocumentosDisponibles();
      }
    });

    this.sessionDestroySub = this.session.onSessionDestroyed$.subscribe(destroyed => {
      if (destroyed) {
        this.resetUI();
      }
    });

    this.ws.connectSocket(); // inicia conexión WebSocket
    this.wsSubscription = this.ws.getMessages().subscribe({
      next: (msg) => this.manejarMensajeWebSocket(msg),
      error: (err) => console.error('❌ Error WebSocket:', err)
    });
  }


  ngAfterViewInit(): void {
    setTimeout(() => this.updateScrollToBottomButtonVisibility(), 0);
    this.syncFeatureFlagsDesdeBackend();
    this.checkASRStatus();
    this.fetchOCRStatus();
    this.initOCRWebSocket();
    this.initASRWebSocket();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }


  ngOnDestroy(): void {
    this.isDestroyed = true;

    if (this.ocrSocket?.readyState === WebSocket.OPEN) {
      this.ocrSocket.close();
    }

    if (this.asrSocket?.readyState === WebSocket.OPEN) {
      this.asrSocket.close();
    }

    this.chatLogic.closeChat();

    this.sessionSubscription?.unsubscribe();
    this.sessionDestroySub?.unsubscribe();
    this.wsSubscription?.unsubscribe();
    this.ws.disconnect(); // cerrar WebSocket correctamente
  }


  iniciar_session(): void {
    this.chatLogic.iniciarSession(state => {
      this.sessionState = state;
      this.cdr.markForCheck();
    });
  }

  listarDocumentosDisponibles(): void {
    const session = this.session.getCurrentSession();
    if (!session?.uuid) return;

    this.messages = this.messages.filter(m => !m.documentSuggestions);
    this.actualizarMensajes();

    this.documentosService.streamSaludoConDocumentos(
      this.messages,
      () => this.actualizarMensajes(),
      mensajeDocs => {
        this.messages.push(mensajeDocs);
        this.actualizarMensajes();
        setTimeout(() => this.scrollToBottom(), 100);
      }
    );
  }

  seleccionarDocumentoCompleto(doc: Documento): void {
    const session = this.session.getCurrentSession();
    if (!session?.uuid) return;

    this.documentoSeleccionadoId = doc.id;
    this.session.setSelectedDocument(doc.id);

    this.messages = this.messages.filter(m => !m.documentSuggestions);

    this.documentosService.streamDescripcionDocumento(
      doc,
      this.messages,
      () => this.actualizarMensajes()
    );

    this.documentosService.asociar(session.uuid, doc.id).subscribe({
      next: () => console.log(`✅ Documento ${doc.id} asociado.`),
      error: err => {
        console.error('❌ Error al asociar documento:', err);
        alert('⚠️ No se pudo asociar el documento.');
      }
    });
  }

  volverAVerDocumentos(): void {
    this.documentoSeleccionadoId = null;
    this.session.setSelectedDocument(null);

    this.messages = this.messages.map(msg =>
      msg.subquestions ? {...msg, subquestions: []} : msg
    );

    this.messages = this.messages.filter(m => !m.documentSuggestions);

    this.documentosService.listar().subscribe({
      next: (docs) => {
        const mensajeDocs = this.documentosService.construirMensajeDeDocumentos(docs);
        this.messages.push(mensajeDocs);
        this.actualizarMensajes();
        this.scrollToBottom();
      },
      error: (err) => {
        console.error('❌ Error cargando documentos:', err);
        const errorMsg: ChatMessage = {
          sender: 'bot',
          text: '⚠️ Lo siento, no pude cargar los documentos disponibles en este momento.'
        };
        this.messages.push(errorMsg);
        this.actualizarMensajes();
      }
    });
  }

  private manejarMensajeWebSocket(msg: ChatSocketMessage): void {
    const respuesta = this.respuestaActual;
    if (!respuesta) return;

    // Descarta lo que llegue tarde de una pregunta anterior. Sin esto, los
    // mensajes rezagados (subpreguntas, ids, audio) se pegaban en la respuesta
    // siguiente y la dejaban cortada o mezclada.
    if (msg.request_id && respuesta.requestId && msg.request_id !== respuesta.requestId) {
      return;
    }

    switch (msg.type) {
      case 'chunk':
        respuesta.text += msg.data;
        this.chatLogic.inactivity.updateActivity();
        respuesta.streaming = false;
        break;

      case 'metadata':
        respuesta.sources = msg.data.sources || [];
        respuesta.subquestions = msg.data.subquestions || [];
        respuesta.showSources = true;
        break;

      case 'response_ids':
        respuesta.question_id = msg.data.question_id;
        respuesta.answer_id = msg.data.answer_id;

        const session = this.session.getCurrentSession();
        if (session) {
          const saved = this.feedback.getFeedback(
            session.uuid,
            msg.data.question_id,
            msg.data.answer_id
          );
          if (saved) respuesta.feedback = saved;
        }
        // No se limpia respuestaActual: las subpreguntas llegan DESPUES de
        // este mensaje y se perdian. El filtro por request_id ya evita que se
        // mezclen respuestas distintas.
        break;

      case 'end':
        respuesta.streaming = false;
        this.isSendActive = false;
        break;

      case 'warn':
        // Antes no habia case: los fallos de TTS se perdian en silencio.
        console.warn('⚠️ Aviso del servidor:', msg.data);
        break;

      case 'error':
        if (msg.type === 'error' && msg.data.includes('finalizado por inactividad')) {
          this.chatLogic.closeChat(true); // ⚠️ sesión vencida
        }

        respuesta.text += `\n⚠️ Error: ${msg.data}`;
        respuesta.streaming = false;
        this.respuestaActual = undefined;
        this.isSendActive = false;
        break;
    }

    this.actualizarMensajes();
  }

  enviarPregunta(preguntaUsuario: string): void {
    this.tts.stop();
    this.isSendActive = true;
    this.isASRActive = true;
    this.isOCRActive = true;

    const session = this.session.getCurrentSession();
    if (!session?.uuid || !this.documentoSeleccionadoId || !preguntaUsuario.trim()) return;

    this.chatLogic.inactivity.updateActivity();

    const pregunta: ChatMessage = {sender: 'user', text: preguntaUsuario};
    this.messages.push(pregunta);

    // Identificador propio de esta pregunta; el backend lo devuelve en cada
    // mensaje para poder emparejarlos.
    const requestId = (globalThis.crypto?.randomUUID?.() ?? String(Date.now() + Math.random()));

    const respuesta: ChatMessage = {
      sender: 'bot',
      text: '',
      sources: [],
      subquestions: [],
      showSources: false,
      streaming: true,
      requestId
    };
    this.respuestaActual = respuesta; // ✅ asignar respuesta actual
    this.messages.push(respuesta);
    this.actualizarMensajes();

    // ✅ Conexión persistente, solo enviar
    this.ws.sendMessage(session.uuid, this.documentoSeleccionadoId, preguntaUsuario, true, requestId);
  }


  onMensajeUsuario(mensaje: string): void {
    this.enviarPregunta(mensaje);
  }

  likeAnswer(questionId: number, answerId: number, message: any): void {
    const sessionUUID = this.sessionState?.uuid;
    if (!sessionUUID || message.feedback) return;

    this.feedback.like(
      sessionUUID,
      questionId,
      answerId,
      () => message.feedback = 'like',
      () => alert('⚠️ Error al registrar like')
    );
  }

  dislikeAnswer(questionId: number, answerId: number, message: any): void {
    const sessionUUID = this.sessionState?.uuid;
    if (!sessionUUID || message.feedback) return;

    this.feedback.dislike(
      sessionUUID,
      questionId,
      answerId,
      () => message.feedback = 'dislike',
      () => alert('⚠️ Error al registrar dislike')
    );
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

  initOCRWebSocket() {
    if (typeof window === 'undefined') return;

    this.ocrSocket = new WebSocket('ws://localhost:8002/ws/status');

    this.ocrSocket.onopen = () => {
      console.log('🟢 WebSocket conectado al servidor de OCR');
    };

    this.ocrSocket.onmessage = (event) => {
      if (this.isDestroyed) {
        console.warn('⚠️ Ignorado: WebSocket recibió mensaje después de destruir el componente');
        return;
      }

      try {
        const data = JSON.parse(event.data);
        if (data.event === 'ocr_changed') {
          console.log('🔄 OCR actualizado por el admin, refrescando estado...');
          this.fetchOCRStatus();
        }
      } catch (e) {
        console.error('❌ Error procesando mensaje WebSocket:', e);
      }
    };

    this.ocrSocket.onerror = (error) => {
      console.error('❌ Error en WebSocket:', error);
    };

    this.ocrSocket.onclose = () => {
      console.warn('🔌 WebSocket cerrado.');
    };
  }


  initASRWebSocket() {
    if (typeof window === 'undefined') return;

    this.asrSocket = new WebSocket('ws://localhost:8001/ws/asr');

    this.asrSocket.onopen = () => {
      console.log('🟢 WebSocket conectado al servidor de ASR');
    };

    this.asrSocket.onmessage = (event) => {
      if (this.isDestroyed) {
        console.warn('⚠️ Ignorado: WebSocket ASR recibió mensaje tras destruir el componente');
        return;
      }

      try {
        const data = JSON.parse(event.data);
        if (data.event === 'asr_changed') {
          console.log('🔄 ASR actualizado por el admin, refrescando estado...');
          this.checkASRStatus();
        }
      } catch (e) {
        console.error('❌ Error procesando mensaje WebSocket ASR:', e);
      }
    };

    this.asrSocket.onerror = (error) => {
      console.error('❌ Error en WebSocket ASR:', error);
    };

    this.asrSocket.onclose = () => {
      console.warn('🔌 WebSocket ASR cerrado.');
    };
  }

  syncFeatureFlagsDesdeBackend(): void {
    this.http.get<any>('http://127.0.0.1:8000/status').subscribe({
      next: (flags) => {
        if (typeof flags.tts_active === 'boolean') {
          this.isTTSActive = flags.tts_active;

          if (isPlatformBrowser(this.platformId)) {
            localStorage.setItem('tts_active', JSON.stringify(this.isTTSActive));
          }
        }

        if (typeof flags.subq_active === 'boolean') {
          this.generateSubquestions = flags.subq_active;

          if (isPlatformBrowser(this.platformId)) {
            localStorage.setItem('subq_active', JSON.stringify(this.generateSubquestions));
          }
        }

        this.cdr.markForCheck();
        console.log("🎛️ Feature flags sincronizados desde backend:", flags);
      },
      error: (err) => {
        console.warn("⚠️ No se pudo obtener el estado de los feature flags:", err);
      }
    });
  }


  resetUI(): void {
    this.messages = [];
    this.session.saveMessages([]);
    this.documentoSeleccionadoId = null;
    this.session.setSelectedDocument(null);

    this.isSendActive = false;
    this.showScrollToBottomButton = false;
    this.isOptionsMenuVisible = false;
    this.haMostradoDocumentos = false;

    this.chatInputComponent?.reset?.();
  }

  actualizarMensajes(): void {
    this.session.saveMessages(this.messages);
    this.cdr.detectChanges();
    this.scrollToBottom();
  }

  onChatScroll(): void {
    this.updateScrollToBottomButtonVisibility();
  }

  updateScrollToBottomButtonVisibility(): void {
    const el = this.chatDisplay.nativeElement;
    const atBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 1;
    this.showScrollToBottomButton = !atBottom;
  }

  scrollToBottomWithArrow(): void {
    this.scrollToBottom();
    this.showScrollToBottomButton = false;
  }

  scrollToBottom(): void {
    try {
      const el = this.chatDisplay.nativeElement;
      el.scrollTop = el.scrollHeight;
      this.updateScrollToBottomButtonVisibility();
    } catch (err) {
      console.error('Scroll error:', err);
    }
  }

  toggleOptionsMenu(): void {
    this.isOptionsMenuVisible = !this.isOptionsMenuVisible;
  }

  @HostListener('document:click', ['$event'])
  onClickOutside(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('.options-menu') && !target.closest('.more-options')) {
      this.isOptionsMenuVisible = false;
    }
  }

  get puedeUsarASR(): boolean {
    const haySesion = !!this.sessionState?.isActive;
    const hayDocumento = !!this.documentoSeleccionadoId;
    return haySesion && hayDocumento && this.isASRActive && !this.isSendActive;
  }

  get puedeUsarOCR(): boolean {
    const haySesion = !!this.sessionState?.isActive;
    const hayDocumento = !!this.documentoSeleccionadoId;
    return haySesion && hayDocumento && this.isOCRActive && !this.isSendActive;
  }

  get puedeEnviarMensaje(): boolean {
    const haySesion = !!this.sessionState?.isActive;
    const hayDocumento = !!this.documentoSeleccionadoId;
    return haySesion && hayDocumento && !this.isSendActive;
  }
}
