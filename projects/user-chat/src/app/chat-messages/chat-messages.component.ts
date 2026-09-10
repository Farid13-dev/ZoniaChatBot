import {Component, Input, Output, EventEmitter, ChangeDetectionStrategy} from '@angular/core';
import { NgClass } from '@angular/common';
import {ChatMessage, Documento} from '../../services/documentos.service'; // Asegúrate de importar correctamente


@Component({
    selector: 'app-chat-messages',
    templateUrl: './chat-messages.component.html',
    styleUrls: ['./chat-messages.component.css'],
    changeDetection: ChangeDetectionStrategy.Eager,
    imports: [NgClass]
})
export class ChatMessagesComponent {
  @Input() messages: ChatMessage[] = [];
  @Input() documentoSeleccionado: boolean = false;
  @Input() documentoSeleccionadoId: number | null = null;

  @Output() onSelectDocumento = new EventEmitter<Documento>();
  @Input() likeAnswer!: (qId: number, aId: number, msg: ChatMessage) => void;
  @Input() dislikeAnswer!: (qId: number, aId: number, msg: ChatMessage) => void;
  @Input() selectSubquestion!: (sub: string) => void;
  @Input() volverAVerDocumentos!: () => void;


  copiedStates: { [index: number]: boolean } = {};
  fadeIn = false;

  selectDocumento(doc: Documento): void {
    this.onSelectDocumento.emit(doc);
  }

  mostrarVolverADocumentos(message: ChatMessage): boolean {
    return Array.isArray(message.subquestions) &&
      message.subquestions.length > 0 &&
      this.documentoSeleccionado;
  }


  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }

  copyToClipboard(text: string, index: number): void {
    navigator.clipboard.writeText(text).then(() => {
      this.copiedStates[index] = true;
      setTimeout(() => {
        this.copiedStates[index] = false;
      }, 2000);
    });
  }
}
