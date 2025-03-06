import { Component } from '@angular/core';
import { ChatService } from '../../services/chat.service';
import {ChatModalComponent} from "../chat-modal/chat-modal.component";

@Component({
  selector: 'app-chat-icon',
  templateUrl: './chat-icon.component.html',
  standalone: true,
  styleUrls: ['./chat-icon.component.css']
})
export class ChatIconComponent {
  constructor(private chatService: ChatService) {}

  openChat() {
    this.chatService.toggleChat();  // Abrir/cerrar chat
  }
}
