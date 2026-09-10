import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { take } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class FeedbackService {
  private readonly FEEDBACK_PREFIX = 'feedback_';

  constructor(private http: HttpClient) {}

  private getKey(sessionUUID: string, questionId: number, answerId: number): string {
    return `${this.FEEDBACK_PREFIX}${sessionUUID}_${questionId}_${answerId}`;
  }

  saveFeedbackLocally(sessionUUID: string, questionId: number, answerId: number, value: 'like' | 'dislike'): void {
    const key = this.getKey(sessionUUID, questionId, answerId);
    localStorage.setItem(key, value);
  }

  getFeedback(sessionUUID: string, questionId: number, answerId: number): 'like' | 'dislike' | null {
    const key = this.getKey(sessionUUID, questionId, answerId);
    return localStorage.getItem(key) as 'like' | 'dislike' | null;
  }

  clearFeedbackForSession(sessionUUID: string): void {
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith(`${this.FEEDBACK_PREFIX}${sessionUUID}_`)) {
        localStorage.removeItem(key);
      }
    });
  }

  like(sessionUUID: string, questionId: number, answerId: number, onSuccess: () => void, onError: () => void): void {
    const payload = { session_uuid: sessionUUID, question_id: questionId, answer_id: answerId };

    this.http.post('http://127.0.0.1:8000/like_answer', payload).pipe(take(1)).subscribe({
      next: () => {
        this.saveFeedbackLocally(sessionUUID, questionId, answerId, 'like');
        onSuccess();
      },
      error: () => onError()
    });
  }

  dislike(sessionUUID: string, questionId: number, answerId: number, onSuccess: () => void, onError: () => void): void {
    const payload = { session_uuid: sessionUUID, question_id: questionId, answer_id: answerId };

    this.http.post('http://127.0.0.1:8000/dislike_answer', payload).pipe(take(1)).subscribe({
      next: () => {
        this.saveFeedbackLocally(sessionUUID, questionId, answerId, 'dislike');
        onSuccess();
      },
      error: () => onError()
    });
  }
}
