// session-timer.service.ts
import {Injectable, NgZone} from '@angular/core';
import {BehaviorSubject} from "rxjs";

@Injectable({providedIn: 'root'})
export class SessionTimerService {
    private timer: any;
    private _active = new BehaviorSubject<boolean>(false);
    readonly isActive$ = this._active.asObservable(); // 🔄 observable externo

    constructor(private ngZone: NgZone) {
    }

    start(startedAt: Date, onTick: (formatted: string) => void): void {
        this.stop();
        this._active.next(true); // ✅ marcar como activo

        this.ngZone.runOutsideAngular(() => {
            this.timer = setInterval(() => {
                const now = new Date();
                const diff = now.getTime() - startedAt.getTime();
                const minutes = Math.floor(diff / 60000);
                const seconds = Math.floor((diff % 60000) / 1000);
                const formatted = `${minutes}m ${seconds < 10 ? '0' : ''}${seconds}s`;

                this.ngZone.run(() => onTick(formatted));
            }, 1000);
        });
    }

    stop(): void {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        this._active.next(false); // ❌ marcar como inactivo
    }
}
