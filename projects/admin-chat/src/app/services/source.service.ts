// src/app/services/source.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class SourceService {
  private baseUrl = 'http://127.0.0.1:8000';

  constructor(private http: HttpClient) {}

  clearSources(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.baseUrl}/clear_sources_to_add`, {});
  }
}
