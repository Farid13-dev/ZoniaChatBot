//projects/user-chat/src/app/chat-input/chat-input.component.ts
import {
  Component, Output, EventEmitter, ViewChild, ElementRef, Input,
  ChangeDetectorRef, ChangeDetectionStrategy, AfterViewChecked,
  Inject, PLATFORM_ID
} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import { isPlatformBrowser, NgClass } from '@angular/common';
import {FormsModule} from "@angular/forms";
import {TTSService} from "../../services/tts.service";

@Component({
    selector: 'app-chat-input',
    templateUrl: './chat-input.component.html',
    styleUrls: ['./chat-input.component.css'],
    changeDetection: ChangeDetectionStrategy.OnPush, // Mejora rendimiento, detección manual
    imports: [NgClass, FormsModule]
})

export class ChatInputComponent implements AfterViewChecked {

  // input and outputs
  @Input() message: string = '';
  @Output() messageSent = new EventEmitter<string>();
  @Input() isASRActive: boolean = true;
  @Input() isSendActive: boolean = false;
  @Input() isOCRActive: boolean = true;

  //element references
  @ViewChild('textarea') textarea!: ElementRef<HTMLTextAreaElement>;
  @ViewChild('waveform', {static: false}) waveform!: ElementRef<HTMLCanvasElement>;

  // estado del componente (UI / grabación, audio, visualización)
  showSendButton: boolean = false;
  recording: boolean = false;
  isPaused: boolean = false;
  showRecordingPanel: boolean = false;

  recordingTime: string = '0:00';
  seconds: number = 0;
  maxRecordingTime = 15;

  animationId?: number;
  recordingInterval: any;

  audioBlob?: Blob;
  recorder: any;
  private RecordRTC: any;
  stream?: MediaStream;

  audioContext?: AudioContext;
  analyser?: AnalyserNode;
  canvasContext: CanvasRenderingContext2D | null = null;
  bufferLength!: number;
  dataArray!: Uint8Array;
  audioErrorMessage: string = '';

  //cargando / procesamiento
  loading: boolean = false;
  processingAudio: boolean = false;
  processingImage: boolean = false;
  floatingMessage: string = '';

  constructor(
    private cdRef: ChangeDetectorRef,
    private http: HttpClient,
    private tts: TTSService,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {
  }

  //ciclo de vida
  async ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      const {default: RecordRTC} = await import('recordrtc');
      this.RecordRTC = RecordRTC;
    }
  }

  ngAfterViewChecked() {
    // Verificar si se está grabando y la visualización de ondas no ha comenzado
    if (this.recording && this.waveform && !this.canvasContext) {
      this.startWaveformVisualization();
    } else {
      // Solo ajustar la altura del textarea y desplazar al final si 'textarea' está definido
      if (this.textarea && this.textarea.nativeElement) {
        this.adjustTextareaHeight();
        this.scrollToBottom(); // Forzar el desplazamiento hacia el final
      }
    }
  }

  //grabación de audio
  async startRecording(event: MouseEvent) {
    this.tts.stop();
    this.resetRecordingUI();
    if (!this.RecordRTC) {
      console.error("RecordRTC aún no está disponible.");
      return;
    }
    if (this.textarea) {
      const textareaEl = this.textarea.nativeElement as HTMLTextAreaElement;
      textareaEl.value = '';
      textareaEl.style.height = '30px';
    }
    this.showSendButton = false; // Ocultar el botón de enviar

    this.showRecordingPanel = true;

// Forzar el render del panel antes de continuar
    setTimeout(() => {
      this.recording = true;
      this.isSendActive = true;
      this.cdRef.markForCheck(); // fuerza la detección de cambios
    }, 0);

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000, // adicional
          channelCount: 1
        }
      });

      this.audioContext = new AudioContext();
      const source = this.audioContext.createMediaStreamSource(this.stream);

      this.analyser = this.audioContext.createAnalyser();
      source.connect(this.analyser);
      this.analyser.fftSize = 2048;
      this.bufferLength = this.analyser.frequencyBinCount;
      this.dataArray = new Uint8Array(this.bufferLength);

      this.recorder = new this.RecordRTC(this.stream, {
        type: 'audio',
        mimeType: 'audio/wav',
        recorderType: this.RecordRTC.StereoAudioRecorder,
        desiredSampRate: 16000,
        numberOfAudioChannels: 1,
        bufferSize: 16384,
        disableLogs: true
      });

      this.recorder.startRecording();

      console.log('Grabación iniciada');
      this.startTimer();
    } catch (error) {
      console.error('Error al acceder al micrófono:', error);
    }
  }

  // pausar, reanudar, cancelar
  pauseRecording() {
    if (this.recording && !this.isPaused && this.recorder) {
      this.isPaused = true;
      this.recorder.pauseRecording();
      this.stopWaveformVisualization();
      console.log('Grabación en pausa');
    }
  }

  resumeRecording() {
    if (this.isPaused && this.recorder) {
      this.isPaused = false;
      this.recorder.resumeRecording();
      this.startWaveformVisualization();
      console.log('Grabación reanudada');
    }
  }

  cancelRecording() {
    if (this.recorder) {
      console.log('Cancelando grabación...');
      this.recorder.stopRecording(() => {
        this.stream?.getTracks().forEach((track) => track.stop());
        this.audioBlob = undefined;
        this.stopTimer();
        this.resetRecordingUI();
        this.isSendActive = false;
        console.log('Grabación cancelada y audio eliminado.');
      });
    }
  }

  //finalizar y enviar audio
  stopAndSendRecording() {
    if (this.recording && this.recorder) {
      console.log('Deteniendo grabación y enviando audio al backend...');
      this.processingAudio = true; // 🔹 Desactiva el botón de subir archivo
      this.recorder.stopRecording(() => {
        this.audioBlob = this.recorder.getBlob();

        if (this.audioBlob && this.audioBlob.size > 0) {
          this.loading = true; // Mostrar el círculo de carga
          this.sendAudioToBackend();
        } else {
          console.error('No se ha generado audioBlob o está vacío.');
          this.processingAudio = false; // 🔹 Reactiva el botón si hay un error
        }

        this.recording = false;
        this.resetRecordingUI();
        this.recorder = null;
      });
    } else {
      console.error('No se está grabando, no hay audio para enviar.');
    }
  }

  sendAudioToBackend() {

    if (this.audioBlob && this.audioBlob.size > 0) {
      const formData = new FormData();
      formData.append('file', this.audioBlob, 'entrada.wav');
      this.processingAudio = true; // Mostrar mensaje de procesamiento de audio

      this.http.post<{ transcription: string }>('http://127.0.0.1:8001/transcribe-audio', formData).subscribe(
        (response) => {
          this.message += response.transcription;
          this.isSendActive = false;
          this.loading = false;
          this.processingAudio = false;
          this.cdRef.markForCheck();
        },
        (error) => {
          console.error('Error al enviar el audio al backend:', error);

          // Detectar mensaje específico de silencio
          const errorMsg = error?.error?.detail || '';
          if (errorMsg.includes('silencioso')) {
            this.audioErrorMessage = 'No se detectó voz en la grabación. Intenta nuevamente.';
          } else {
            this.audioErrorMessage = 'Ocurrió un error al transcribir el audio.';
          }

          // Resetear estados visuales
          this.isSendActive = false;
          this.loading = false;
          this.processingAudio = false;

          // Ocultar mensaje tras 4 segundos
          setTimeout(() => {
            this.audioErrorMessage = '';
            this.cdRef.markForCheck();
          }, 4000);

          this.cdRef.markForCheck();
        }
      );

    } else {
      console.error('No hay audio disponible para enviar');
      this.processingAudio = false; // 🔹 Reactiva el botón si no hay audio
    }
  }

  //visualización de ondas

  startWaveformVisualization() {
    if (this.waveform && this.analyser) {
      const canvas = this.waveform.nativeElement;
      this.canvasContext = canvas.getContext('2d');

      if (!this.canvasContext) {
        console.error('El canvas no está disponible para la visualización.');
        return;
      }

      const WIDTH = canvas.width;
      const HEIGHT = canvas.height;

      this.canvasContext.clearRect(0, 0, WIDTH, HEIGHT);

      this.analyser.fftSize = 1024;
      const bufferLength = this.analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const draw = () => {
        if (!this.recording || !this.canvasContext || !this.analyser) {
          return;
        }

        this.analyser.getByteTimeDomainData(dataArray);
        this.canvasContext.clearRect(0, 0, WIDTH, HEIGHT);

        const gradient = this.canvasContext.createLinearGradient(0, 0, WIDTH, 0);
        gradient.addColorStop(0, 'rgba(236, 112, 99, 0.9)');
        gradient.addColorStop(1, 'rgba(236, 112, 99, 0.2)');

        this.canvasContext.strokeStyle = gradient;
        this.canvasContext.lineWidth = 4;
        this.canvasContext.lineCap = 'round';

        this.canvasContext.beginPath();
        const sliceWidth = WIDTH / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const v = dataArray[i] / 128.0;
          const y = (v * HEIGHT) / 2;

          if (i === 0) {
            this.canvasContext.moveTo(x, y);
          } else {
            this.canvasContext.lineTo(x, y);
          }

          x += sliceWidth;
        }

        this.canvasContext.lineTo(WIDTH, HEIGHT / 2);
        this.canvasContext.stroke();

        if (!this.isPaused) {
          this.animationId = requestAnimationFrame(draw);
        }
      };

      this.animationId = requestAnimationFrame(draw);
    }
  }

  stopWaveformVisualization() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }
  }

  //temporizador de grabación

  startTimer() {
    this.stopTimer(); // Detener cualquier temporizador previo
    this.recordingInterval = setInterval(() => {
      if (!this.isPaused) {
        this.seconds++;
        const mins = Math.floor(this.seconds / 60);
        const secs = this.seconds % 60;
        this.recordingTime = `${mins}:${this.padTime(secs)}`;
        this.cdRef.markForCheck();

        // Detener grabación si se alcanza el tiempo máximo
        if (this.seconds >= this.maxRecordingTime) {
          console.log(`Tiempo máximo de grabación alcanzado (${this.maxRecordingTime} segundos). Deteniendo grabación.`);
          this.stopAndSendRecording();
        }
      }
    }, 1000);
  }

  stopTimer() {
    if (this.recordingInterval) {
      clearInterval(this.recordingInterval);
    }
  }

  padTime(value: number) {
    return value < 10 ? `0${value}` : value.toString();
  }

  //Reset UI despues de grabar
  resetRecordingUI() {
    this.showRecordingPanel = false;
    this.recording = false;
    this.isPaused = false;
    this.seconds = 0;
    this.recordingTime = '0:00';
    this.stopTimer();
    this.stopWaveformVisualization();
    // Limpiar el input de texto cuando se comienza una nueva grabación
    this.message = '';

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
    }

    if (this.audioContext) {
      this.audioContext.close();
    }

    this.audioContext = undefined;
    this.analyser = undefined;
    this.canvasContext = null;

    this.cdRef.markForCheck();  // Desacoplar la actualización de la vista
  }

  //carga y ocr de imágenes
  // Método para manejar la selección de imagen
  onImageSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        this.displayFloatingMessage("El archivo no es una imagen válida.");
        return;
      }

      if (file.size > 2 * 1024 * 1024) {
        this.displayFloatingMessage("La imagen no debe superar los 2 MB.");
        return;
      }

      this.loading = true;
      this.uploadImage(file);
    }
  }


  displayFloatingMessage(msg: string) {
    this.floatingMessage = msg;
    setTimeout(() => {
      this.floatingMessage = '';
      this.cdRef.markForCheck(); // actualizar con OnPush
    }, 4000);
    this.cdRef.markForCheck();
  }

  // Método para subir la imagen al backend
  uploadImage(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    this.tts.stop();
    this.processingImage = true;
    this.isSendActive = true;
    this.message = '';
    // Configuramos el timeout para la petición HTTP
    const timeout = 20000; // 10 segundos
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Tiempo de procesamiento excedido')), timeout)
    );

    const ocrRequest = this.http.post<{ text: string }>('http://127.0.0.1:8002/ocr', formData).toPromise();

    Promise.race([ocrRequest, timeoutPromise])
      .then((response: any) => {
        const extractedText = response.text?.trim();

        if (!extractedText) {
          this.displayFloatingMessage("No se detectó texto en la imagen.");
          this.loading = false;
          this.processingImage = false;
          this.isSendActive = false;
          return;
        }

        this.message = extractedText;
        this.loading = false;
        this.processingImage = false;
        this.showSendButton = true;
        this.isSendActive = false;
        this.adjustTextareaHeight();
        this.cdRef.markForCheck();
        this.scrollToBottom();
      })
      .catch((error) => {
        console.error('Error al procesar la imagen:', error);
        this.loading = false;
        this.processingImage = false;
        this.isSendActive = false;

        if (error.message === 'Tiempo de procesamiento excedido' || error.status === 408) {
          this.displayFloatingMessage("El procesamiento de la imagen tomó demasiado tiempo. Intente con una imagen más simple.");
        } else {
          this.displayFloatingMessage("Error al procesar la imagen. Inténtelo nuevamente.");
        }
      });
  }

  //manejo de mensajes
  sendMessage() {
    if (!this.isSendActive && this.message?.trim() !== '') {
      this.messageSent.emit(this.message);
      this.message = '';
      if (this.textarea) {
        const textareaEl = this.textarea.nativeElement as HTMLTextAreaElement;
        textareaEl.value = '';
        textareaEl.style.height = '30px';
      }
      this.showSendButton = false;
    }
  }

  handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      if (this.isSendActive) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      this.sendMessage();
    }
  }

  //ui helpers

  toggleButtons() {
    this.showSendButton = this.message?.trim().length > 0;
  }

  // Método para ajustar la altura del textarea y activar el desplazamiento hacia abajo
  adjustTextareaHeight() {
    const textarea = this.textarea.nativeElement;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }

  // Desplaza el textarea hacia abajo cuando hay texto adicional
  scrollToBottom() {
    const textarea = this.textarea.nativeElement;
    textarea.scrollTop = textarea.scrollHeight;
  }

// Limpieza general del input (usado al cerrar sesión)
  reset(): void {
    this.message = '';
    this.showSendButton = false;

    // Reset visual del textarea
    if (this.textarea?.nativeElement) {
      const textareaEl = this.textarea.nativeElement as HTMLTextAreaElement;
      textareaEl.value = '';
      textareaEl.style.height = '30px';
    }

    this.cdRef.markForCheck(); // Importante con OnPush
  }

}
