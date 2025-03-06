import {
  Component,
  Output,
  EventEmitter,
  ViewChild,
  ElementRef,
  Input,
  ChangeDetectorRef,
  ChangeDetectionStrategy,
  AfterViewChecked
} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import RecordRTC from 'recordrtc';
import {NgClass, NgIf} from "@angular/common";
import {FormsModule} from "@angular/forms";

@Component({
  selector: 'app-chat-input',
  templateUrl: './chat-input.component.html',
  styleUrls: ['./chat-input.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,  // Estrategia OnPush para mejorar el rendimiento
  imports: [
    NgClass,
    FormsModule,
    NgIf
  ],
  standalone: true
})
export class ChatInputComponent implements AfterViewChecked {
  @Input() message: string = ''; // Asignar una cadena vacía por defecto
  @Output() messageSent = new EventEmitter<string>();
  @Input() isASRActive: boolean = true; // Estado del ASR, recibido desde el componente principal
  showSendButton: boolean = false;
  recording: boolean = false;
  isPaused: boolean = false;
  showRecordingPanel: boolean = false;
  recordingTime: string = '0:00';
  recordingInterval: any;
  audioBlob: Blob | undefined;
  recorder: any;
  stream: MediaStream | undefined;
  seconds: number = 0;
  audioContext: AudioContext | undefined;
  analyser: AnalyserNode | undefined;
  canvasContext: CanvasRenderingContext2D | null = null;
  bufferLength!: number;
  dataArray!: Uint8Array;
  @Input() transcribing: boolean = false;
  animationId: number | undefined;
  // Nueva propiedad para manejar el estado de carga
  loading: boolean = false;
  processingAudio: boolean = false;
  processingImage: boolean = false;
  maxRecordingTime = 15;
  @ViewChild('textarea') textarea!: ElementRef<HTMLTextAreaElement>;

  @ViewChild('waveform', {static: false}) waveform!: ElementRef<HTMLCanvasElement>;

  constructor(private cdRef: ChangeDetectorRef, private http: HttpClient) {
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


  async startRecording(event: MouseEvent) {
    this.resetRecordingUI();

    if (this.textarea) {
      const textareaEl = this.textarea.nativeElement as HTMLTextAreaElement;
      textareaEl.value = '';
      textareaEl.style.height = '30px';
    }
    this.showSendButton = false; // Ocultar el botón de enviar

    this.showRecordingPanel = true;
    this.recording = true;
    this.transcribing = true;  // Disable buttons while recording

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({audio: true});
      this.audioContext = new AudioContext();
      const source = this.audioContext.createMediaStreamSource(this.stream);

      this.analyser = this.audioContext.createAnalyser();
      source.connect(this.analyser);
      this.analyser.fftSize = 2048;
      this.bufferLength = this.analyser.frequencyBinCount;
      this.dataArray = new Uint8Array(this.bufferLength);

      this.recorder = new RecordRTC(this.stream, {type: 'audio', mimeType: 'audio/wav'});
      this.recorder.startRecording();

      console.log('Grabación iniciada');
      this.startTimer();
    } catch (error) {
      console.error('Error al acceder al micrófono:', error);
    }
  }


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

  stopAndSendRecording() {
    if (this.recording && this.recorder) {
      console.log('Deteniendo grabación y enviando audio al backend...');
      this.recorder.stopRecording(() => {
        this.audioBlob = this.recorder.getBlob();

        if (this.audioBlob && this.audioBlob.size > 0) {
          this.loading = true; // Mostrar el círculo de carga
          this.sendAudioToBackend();
        } else {
          console.error('No se ha generado audioBlob o está vacío.');
        }

        this.recording = false;
        this.resetRecordingUI();
      });
    } else {
      console.error('No se está grabando, no hay audio para enviar.');
    }
  }

  sendAudioToBackend() {
    if (this.audioBlob && this.audioBlob.size > 0) {
      const formData = new FormData();
      formData.append('file', this.audioBlob, 'recording.wav');
      this.processingAudio = true; // Mostrar mensaje de procesamiento de audio

      this.http.post<{ transcription: string }>('http://127.0.0.1:8001/transcribe-audio', formData).subscribe(
        (response) => {
          this.message += response.transcription;
          this.transcribing = false;
          this.loading = false;  // Ocultar el círculo de carga
          this.processingAudio = false; // Ocultar mensaje de procesamiento de audio
          this.cdRef.markForCheck();  // Actualiza la vista sin bloquear el hilo principal
        },
        (error) => {
          console.error('Error al enviar el audio al backend:', error);
          this.transcribing = false;
          this.processingAudio = false; // Ocultar mensaje en caso de error
          this.cdRef.markForCheck();
        }
      );
    } else {
      console.error('No hay audio disponible para enviar');
    }
  }

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
        this.transcribing = false;
        console.log('Grabación cancelada y audio eliminado.');
      });
    }
  }

  toggleButtons() {
    this.showSendButton = this.message?.trim().length > 0;
  }

// Método para manejar la selección de imagen
  onImageSelected(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) {
      if (file.size > 2 * 1024 * 1024) { // Verificar tamaño de archivo (2 MB)
        alert("La imagen no debe superar los 2 MB.");
        return;
      }

      this.loading = true;  // Mostrar el spinner de carga
      this.uploadImage(file);
    }
  }

  // Método para subir la imagen al backend
  uploadImage(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    this.processingImage = true; // Mostrar mensaje de procesamiento de imagen
    this.transcribing = true;
    this.http.post<{ text: string }>('http://127.0.0.1:8003/ocr', formData).subscribe({
      next: (response) => {
        this.message = response.text;  // Mostrar el texto extraído en el textarea
        this.loading = false;          // Ocultar el spinner
        this.processingImage = false; // Ocultar mensaje de procesamiento de imagen
        this.showSendButton = true;    // Mostrar el botón de enviar
        this.transcribing = false;
        this.adjustTextareaHeight()
        this.cdRef.markForCheck();
        this.scrollToBottom(); // Desplaza hacia abajo para mostrar el texto más reciente

      },
      error: (error) => {
        console.error('Error al procesar la imagen:', error);
        this.loading = false;  // Ocultar el spinner en caso de error
        this.processingImage = false; // Ocultar mensaje en caso de error
        this.transcribing = true;
        alert("Error al procesar la imagen. Inténtelo nuevamente.");
      }
    });
  }

  sendMessage() {
    if (!this.transcribing && this.message?.trim() !== '') {
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

  focusTextarea() {
    if (this.textarea) {
      const textareaEl = this.textarea.nativeElement as HTMLTextAreaElement;
      textareaEl.focus();
      textareaEl.setSelectionRange(this.message?.length || 0, this.message?.length || 0);
    }
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

  handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      if (this.transcribing) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      this.sendMessage();
    }
  }
}
