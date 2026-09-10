import {Injectable, Inject, PLATFORM_ID} from '@angular/core';
import {isPlatformBrowser} from '@angular/common';

@Injectable({providedIn: 'root'})
export class TTSService {
  private isBrowser: boolean;
  private audioContext?: AudioContext;
  private audioQueue: AudioBuffer[] = [];
  private isPlaying = false;
  private currentSource: AudioBufferSourceNode | null = null;

  constructor(@Inject(PLATFORM_ID) platformId: Object) {
    this.isBrowser = isPlatformBrowser(platformId);
    if (this.isBrowser) {
      this.audioContext = new AudioContext();
    }
  }

  playBase64Audio(base64: string): void {
    if (!this.isBrowser || !this.audioContext) return;

    const binary = atob(base64);
    const buffer = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      buffer[i] = binary.charCodeAt(i);
    }

    this.audioContext.decodeAudioData(buffer.buffer, (decoded) => {
      this.audioQueue.push(decoded);
      this.playNext();
    }, (error) => {
      console.error('Error decoding audio:', error);
    });
  }

  private playNext(): void {
    if (!this.audioContext || this.isPlaying || this.audioQueue.length === 0) return;

    const nextBuffer = this.audioQueue.shift();
    if (!nextBuffer) return;

    const source = this.audioContext.createBufferSource();
    source.buffer = nextBuffer;
    source.connect(this.audioContext.destination);
    source.onended = () => {
      this.isPlaying = false;
      this.playNext();
    };

    this.currentSource = source;
    this.isPlaying = true;
    source.start(0);
  }

  stop(): void {
    if (!this.isBrowser || !this.currentSource) return;

    this.currentSource.stop();
    this.currentSource.disconnect();
    this.currentSource = null;
    this.audioQueue = [];
    this.isPlaying = false;
  }
}
