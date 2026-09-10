import { ComponentFixture, TestBed } from '@angular/core/testing';

import { InitializeQaComponent } from './initialize-qa.component';

describe('InitializeQaComponent', () => {
  let component: InitializeQaComponent;
  let fixture: ComponentFixture<InitializeQaComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InitializeQaComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(InitializeQaComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
