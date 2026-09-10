import {Component, ChangeDetectionStrategy} from '@angular/core';
import {ChatLogicService} from '../../services/chat-logic.service';

@Component({
  selector: 'app-chat-icon',
  templateUrl: './chat-icon.component.html',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Eager,
  styleUrls: ['./chat-icon.component.css']
})
export class ChatIconComponent {
  constructor(private chatService: ChatLogicService) {
  }

  openChat(): void {
    if (this.chatService.isDestroyed) {
      this.chatService.resetChat();
      this.chatService.restoreSessionState();
    }

    this.chatService.toggleChat();
  }
}

