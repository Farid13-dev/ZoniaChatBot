// chat-modal.component.ts
import {Component, ViewChild, QueryList, ElementRef, Renderer2, ViewChildren, AfterViewInit} from '@angular/core';
import {ChatMessagesComponent} from '../chat-messages/chat-messages.component';
import {ChatInputComponent} from '../chat-input/chat-input.component';
import {ChatService} from '../../services/chat.service';
import {NgClass, NgIf, NgOptimizedImage} from '@angular/common';
import {HttpClient} from "@angular/common/http";

@Component({
  selector: 'app-chat-modal',
  templateUrl: './chat-modal.component.html',
  standalone: true,
  imports: [
    ChatMessagesComponent,
    ChatInputComponent,
    NgIf,
    NgOptimizedImage,
    NgClass,
  ],
  styleUrls: ['./chat-modal.component.css'],
})
export class ChatModalComponent implements AfterViewInit {
  @ViewChild('chatModal', {static: true}) chatModal!: ElementRef;
  @ViewChild('chatDisplay', {static: true}) chatDisplay!: ElementRef;
  @ViewChild(ChatInputComponent) chatInputComponent!: ChatInputComponent;
  @ViewChildren('messageElement') messageElements!: QueryList<ElementRef>;

  isOpen: boolean = false;
  isNavigatingEditHistory: boolean = false;
  shouldScrollToBottom = true;
  showScrollToBottomButton = false;
  transcribing: boolean = false;  // Agregar estado para controlar los botones
  isBotThinking: boolean = false;
  messages: {
    history: string[],
    currentIndex: number
  }[] = [
    {history: ['Hola, ¿cómo estás?'], currentIndex: 0}
  ];

  messageToEdit: { message: string, index: number } | null = null;
  isOptionsMenuVisible: boolean = false;
  isASRActive: boolean = true; // Estado inicial del ASR (activo)
  isTTSActive: boolean = true;  // Estado inicial de TTS activo


  constructor(private chatService: ChatService, private renderer: Renderer2, private http: HttpClient) {
    this.chatService.chatState.subscribe((state) => {
      this.isOpen = state;
    });
  }

  ngAfterViewInit() {
    this.updateScrollToBottomButtonVisibility();
  }

  onChatScroll() {
    this.updateScrollToBottomButtonVisibility();
  }

  private updateScrollToBottomButtonVisibility() {
    const element = this.chatDisplay.nativeElement;
    const atBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 1;
    this.showScrollToBottomButton = !atBottom;
  }

  scrollToBottomWithArrow() {
    this.scrollToBottom();
    this.showScrollToBottomButton = false;
  }

  private scrollToMessage(index: number): Promise<void> {
    return new Promise<void>((resolve) => {
      try {
        const messageElements = this.messageElements.toArray();
        if (messageElements[index]) {
          const messageElement = messageElements[index].nativeElement;
          messageElement.scrollIntoView({behavior: 'smooth', block: 'center'});
          requestAnimationFrame(() => {
            this.shouldScrollToBottom = false;
            this.isNavigatingEditHistory = true;
            resolve();
          });
        } else {
          resolve();
        }
      } catch (err) {
        console.error('Error al centrar el mensaje:', err);
        resolve();
      }
    });
  }

  private scrollToBottom(): void {
    try {
      const element = this.chatDisplay.nativeElement;
      element.scrollTop = element.scrollHeight;
      this.updateScrollToBottomButtonVisibility();
    } catch (err) {
      console.error('Error al desplazar al final:', err);
    }
  }


  // Método para enviar un nuevo mensaje o editar uno existente
  sendMessage(message: string) {
    this.transcribing = true;
    this.isBotThinking = true;

    if (this.messageToEdit) {
      const msg = this.messages[this.messageToEdit.index];
      msg.history.push(message);
      msg.currentIndex = msg.history.length - 1;
      this.messageToEdit = null;
    } else {
      this.messages.push({ history: [message], currentIndex: 0 });
    }

    this.shouldScrollToBottom = true;
    this.isNavigatingEditHistory = false;

    const botMessageIndex = this.messages.length;
    this.messages.push({ history: [""], currentIndex: 0 });

    let previousChunk = "";
    this.chatService.sendMessageStream(message).subscribe({
      next: (chunk: string) => {
        const newContent = chunk.replace(previousChunk, "");
        previousChunk = chunk;

        this.messages[botMessageIndex].history[0] = this.messages[botMessageIndex].history[0].replace("...", "") + newContent;
        this.isBotThinking = false;
        this.scrollToBottom();
      },
      complete: () => {
        this.transcribing = false;
        this.isBotThinking = false;
        const botResponse = this.messages[botMessageIndex].history[0];
        if (this.isTTSActive) {
          this.playAudioResponse(botResponse);  // Reproduce la respuesta como audio
        }
        this.scrollToBottom();
      },
      error: (error) => {
        console.error('Error al enviar el mensaje al backend:', error);
        this.transcribing = false;
        this.isBotThinking = false;
      }
    });

    setTimeout(() => {
      requestAnimationFrame(() => {
        this.scrollToBottom();
      });
    }, 0);
  }


  handleEditMessage(event: { message: string, index: number }) {
    this.shouldScrollToBottom = false;
    this.isNavigatingEditHistory = true;
    this.messageToEdit = event;
    this.chatInputComponent.message = event.message;
    this.scrollToMessage(event.index).then(() => {
      this.chatInputComponent.focusTextarea();
    });
  }

  showPreviousEdition(index: number) {
    if (this.messages[index].currentIndex > 0) {
      this.isNavigatingEditHistory = true;
      this.shouldScrollToBottom = false;
      this.messages[index].currentIndex--;

      setTimeout(() => {
        this.scrollToMessage(index);
      }, 0);
    }
  }

  showNextEdition(index: number) {
    const msg = this.messages[index];
    if (msg.currentIndex < msg.history.length - 1) {
      this.isNavigatingEditHistory = true;
      this.shouldScrollToBottom = false;
      this.messages[index].currentIndex++;

      setTimeout(() => {
        this.scrollToMessage(index);
      }, 0);
    }
  }


  closeChat() {
    this.chatService.toggleChat();
  }

  // Método para mostrar/ocultar el menú de opciones
  toggleOptionsMenu() {
    this.isOptionsMenuVisible = !this.isOptionsMenuVisible;
  }

  // Ejemplo de métodos para manejar cada opción
  toggleASR() {
    this.isASRActive = !this.isASRActive;
    this.http.post('http://127.0.0.1:8001/toggle-asr', {state: this.isASRActive}).subscribe({
      next: (response) => console.log("ASR estado:", response),
      error: (error) => console.error("Error al cambiar el estado del ASR:", error)

    });
    this.isOptionsMenuVisible = false;
  }

 // Reproduce la respuesta del bot utilizando el servicio TTS
  playAudioResponse(text: string) {
    const requestPayload = {
      lang: "es",
      tts_text: text,
      temperature: 0.3,
      length_penalty: 1.0,
      repetition_penalty: 1.5,
      top_k: 80,
      top_p: 0.95,
      sentence_split: false,
      use_config: false
    };

    this.http.post('http://127.0.0.1:8002/tts_stream', requestPayload, { responseType: 'blob' })
      .subscribe((audioBlob) => {
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.play();
      }, error => console.error("Error al obtener el audio TTS:", error));
  }
  toggleTTS() {
    this.isTTSActive = !this.isTTSActive;
    this.http.post('http://127.0.0.1:8002/toggle-tts', {state: this.isTTSActive}).subscribe({
      next: (response) => console.log("TTS estado:", response),
      error: (error) => console.error("Error al cambiar el estado del TTS:", error)

    });
    this.isOptionsMenuVisible = false;
  }

  rateOperator() {
    // Lógica para calificar al operador
    console.log("Calificar operador");
    this.isOptionsMenuVisible = false;
  }

}
