import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ProcessDocsComponent } from './process-docs.component';

describe('ProcessDocsComponent', () => {
  let component: ProcessDocsComponent;
  let fixture: ComponentFixture<ProcessDocsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProcessDocsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ProcessDocsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
