// En ChatMessagesComponent
import { Component, Input, Output, EventEmitter } from '@angular/core';
import { NgClass, NgForOf, NgIf } from '@angular/common';

@Component({
  selector: 'app-chat-messages',
  templateUrl: './chat-messages.component.html',
  standalone: true,
  imports: [
    NgForOf,
    NgClass,
    NgIf
  ],
  styleUrls: ['./chat-messages.component.css']
})
export class ChatMessagesComponent {
  @Input() messages: {
    history: string[],
    currentIndex: number
  }[] = [];  // Cambiar el tipo de mensajes

  @Output() editMessage = new EventEmitter<{ message: string, index: number }>(); // Emitir evento para editar mensaje
  @Output() swipeLeft = new EventEmitter<number>();
  @Output() swipeRight = new EventEmitter<number>();
 @Input() isBotThinking: boolean = false; // Añadir la propiedad para recibir el estado

  // Método para emitir el evento de edición
  onEditMessage(message: { history: string[], currentIndex: number }, index: number) {
    this.editMessage.emit({ message: message.history[message.currentIndex], index });
  }
}
