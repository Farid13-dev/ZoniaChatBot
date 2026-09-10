import { Component, ChangeDetectionStrategy } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ChatIconComponent } from "./chat-icon/chat-icon.component";
import { ChatModalComponent } from "./chat-modal/chat-modal.component";

import { HttpClientModule } from '@angular/common/http';

@Component({
    selector: 'app-root',
    imports: [
    RouterOutlet,
    ChatIconComponent,
    ChatModalComponent,
    HttpClientModule
],
    templateUrl: './app.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'ZoniaChatBot';
}
