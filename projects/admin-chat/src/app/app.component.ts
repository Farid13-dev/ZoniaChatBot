import { Component, OnInit, Inject, PLATFORM_ID, ChangeDetectionStrategy } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

import { CommonModule } from '@angular/common';
import { UploadPdfComponent } from './upload-pdf/upload-pdf.component';
import { ProcessDocsComponent } from './process-docs/process-docs.component';
import { InitializeQaComponent } from './initialize-qa/initialize-qa.component';
import { ChatbotComponent } from './chatbot/chatbot.component';

@Component({
    selector: 'app-root',
    imports: [
        CommonModule,
        UploadPdfComponent,
        ProcessDocsComponent,
        InitializeQaComponent,
        ChatbotComponent
    ],
    templateUrl: './app.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  tabs = [
    { label: "📂 UPLOAD PDF" },
    { label: "⚙️ CONFIG QA" },
    { label: "🤖 INITIALIZE QA" },
    { label: "💬 CHATBOT" }
  ];

  selectedTab: number = 0;
  renderChatbot = false;

  constructor(@Inject(PLATFORM_ID) private platformId: Object) {}

  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      const savedTab = localStorage.getItem('selectedTab');
      if (savedTab !== null) {
        const parsed = +savedTab;
        if (parsed === 3) {
          // ⚠️ Retrasa carga del chatbot si fue la última abierta
          setTimeout(() => {
            this.selectedTab = parsed;
            this.renderChatbot = true;
          }, 50);
        } else {
          this.selectedTab = parsed;
        }
      }
    }
  }

  selectTab(index: number) {
    this.selectedTab = index;
    localStorage.setItem('selectedTab', index.toString());

    // 🧠 Solo renderiza chatbot si es seleccionado manualmente
    this.renderChatbot = index === 3;
  }
}
