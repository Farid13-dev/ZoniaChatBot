import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors, withFetch, withXhr } from '@angular/common/http';
import { provideClientHydration, withNoIncrementalHydration } from '@angular/platform-browser';
import { routes } from './app.routes';
import { importProvidersFrom } from '@angular/core';
import { QuillModule } from 'ngx-quill';
export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideClientHydration(withNoIncrementalHydration()),
    provideHttpClient(withXhr(), withInterceptors([])),
    provideHttpClient(withFetch()),
     importProvidersFrom(
      QuillModule.forRoot()  // ✅ Aquí va la configuración del editor
    )
  ]
};
