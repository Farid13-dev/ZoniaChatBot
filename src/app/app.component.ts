import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ChatIconComponent } from "./components/chat-icon/chat-icon.component";
import { ChatModalComponent } from "./components/chat-modal/chat-modal.component";
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';  // Asegúrate de que está importado
import { provideHttpClient } from '@angular/common/http';
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, ChatIconComponent, ChatModalComponent, CommonModule, HttpClientModule], // Asegúrate de que está aquí
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'ZoniaChatBot';
}
