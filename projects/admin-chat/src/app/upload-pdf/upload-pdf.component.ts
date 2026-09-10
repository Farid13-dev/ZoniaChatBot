import {Component, OnInit, ChangeDetectionStrategy} from '@angular/core';

import {HttpClient, HttpClientModule} from '@angular/common/http';
import {FormsModule} from '@angular/forms';
import {QuillModule} from 'ngx-quill';

@Component({
    selector: 'app-upload-pdf',
    imports: [HttpClientModule, FormsModule, QuillModule],
    templateUrl: './upload-pdf.component.html',
    changeDetection: ChangeDetectionStrategy.Eager,
    styleUrls: ['./upload-pdf.component.css']
})
export class UploadPdfComponent implements OnInit {
  selectedFile: File | null = null;
  category: string = '';
  sourceUrl: string = ''; // URL opcional
  sourcesToAdd: string[] = []; // Fuentes pendientes de subir
  loading = false;
  uploadedPdfs: { id: number, name: string, category: string }[] = []; // ✅ Agregado el id y corregido `category`
  selectedSource: string = ''; // ✅ Nueva variable para seleccionar archivo de 'uploads'
  sqliteCategory: string = ''; // ✅ Nueva variable para ingresar categoría
  sqliteDescripcion: string = ''; // ✅ Nueva variable para ingresar categoría

  // Modal y Quill
  isEditModalOpen = false;
  editForm = {id: 0, name: '', categoria: '', descripcion: ''};
  quillModules = {
    toolbar: [
      [{'font': []}],
      [{'size': ['small', false, 'large', 'huge']}],
      ['bold', 'italic', 'underline', 'strike'],
      [{'script': 'sub'}, {'script': 'super'}],
      [{'header': 1}, {'header': 2}],
      [{'list': 'ordered'}, {'list': 'bullet'}],
      [{'align': []}],          // ✅ Alineación (incluye justificar)
      ['blockquote', 'code-block'],
      ['clean']
    ]
  };

  milvusDocs: { document_id: string; metadata: { file_name?: string } }[] = [];

  constructor(private http: HttpClient) {
  }

  ngOnInit() {
    this.listUploadedFiles();
    this.listSqliteFiles();
    this.listarMilvusDocuments();
  }

  // Seleccionar un archivo
  onFileSelected(event: Event) {
    const fileInput = event.target as HTMLInputElement;
    if (fileInput.files && fileInput.files.length > 0) {
      this.selectedFile = fileInput.files[0];

      if (!['application/pdf', 'text/csv'].includes(this.selectedFile.type)) {
        alert('⚠️ Solo se permiten archivos PDF o CSV.');
        this.selectedFile = null;
        fileInput.value = '';
      }
    }
  }

// 📌 Incluir una fuente (archivo o URL)
  includeSource() {
    if (!this.selectedFile && !this.sourceUrl.trim()) {
      alert('⚠️ Debe seleccionar un archivo o ingresar una URL.');
      return;
    }

    const formData = new FormData();
    if (this.selectedFile) {
      formData.append('file', this.selectedFile);
    }
    if (this.sourceUrl) {
      formData.append('include_url', this.sourceUrl);
    }

    this.loading = true;
    this.http.post<{ message: string, sources_to_add: string[] }>('http://127.0.0.1:8000/include_source', formData)
      .subscribe(
        (response) => {
          alert(response.message);
          this.sourcesToAdd = response.sources_to_add;

          // ✅ Limpiar la selección del archivo y el input
          this.selectedFile = null;
          this.sourceUrl = '';
          (document.getElementById('fileInput') as HTMLInputElement).value = '';

          this.loading = false;
          this.listUploadedFiles(); // 🔄 Recargar lista automáticamente
        },
        (error) => {
          console.error('Error al incluir fuente:', error);

          // ✅ Limpiar los valores incluso si hay un error
          this.selectedFile = null;
          this.sourceUrl = '';
          (document.getElementById('fileInput') as HTMLInputElement).value = '';

          this.loading = false;
        }
      );
  }

  // Listar archivos en la ruta 'uploads'
  listUploadedFiles() {
    this.loading = true;
    this.http.get<{ files: string[] }>('http://127.0.0.1:8000/list_uploaded_files')
      .subscribe(
        (response) => {
          this.sourcesToAdd = response.files || []; // ✅ Manejar el caso en que `files` sea undefined
          this.loading = false;
        },
        (error) => {
          console.error('Error al listar archivos:', error);
          this.sourcesToAdd = [];
          this.loading = false;
        }
      );
  }

  // Limpiar fuentes
  clearSources() {
    this.loading = true;
    this.http.post<{ message: string }>('http://127.0.0.1:8000/clear_sources_to_add', {})
      .subscribe(
        (response) => {
          alert(response.message);
          this.sourcesToAdd = [];
          this.loading = false;
          this.listUploadedFiles(); // 🔄 Recargar lista automáticamente
        },
        (error) => {
          console.error('Error al limpiar fuentes:', error);
          this.loading = false;
        }
      );
  }

  // Eliminar archivo específico
  deleteFile(filename: string) {
    this.loading = true;
    this.http.delete<{ message: string }>(`http://127.0.0.1:8000/delete_uploaded_file/${filename}`)
      .subscribe(
        (response) => {
          alert(response.message);
          this.listUploadedFiles(); // 🔄 Recargar lista automáticamente
          this.loading = false;
        },
        (error) => {
          console.error('Error al eliminar archivo:', error);
          this.loading = false;
        }
      );
  }

  // 📌 Subir un archivo de la carpeta 'uploads' a SQLite
  uploadToSQLite() {
    if (!this.selectedSource || !this.sqliteCategory.trim()) {
      alert("⚠️ Debe seleccionar un archivo y proporcionar una categoría.");
      return;
    }

    const formData = new FormData();
    formData.append("filename", this.selectedSource);
    formData.append("categoria", this.sqliteCategory);
    formData.append("descripcion", this.sqliteDescripcion);

    this.loading = true;

    this.http.post<{ message: string, file_id?: number }>('http://127.0.0.1:8000/upload_source_to_sqlite', formData)
      .subscribe(
        (response) => {
          alert(response.message);
          this.sqliteCategory = '';
          this.sqliteDescripcion = '';
          this.selectedSource = '';

          this.listSqliteFiles(); // 🔄 Recargar lista automáticamente
          this.loading = false;
        },
        (error) => {
          console.error("Error al subir a SQLite:", error);

          // 📌 Si el archivo ya existe, mostrar un mensaje adecuado
          if (error.status === 400 && error.error.detail === "El archivo ya existe en la base de datos.") {
            alert("⚠️ El archivo ya se encuentra en la base de datos.");
          } else {
            alert("❌ Error al subir el archivo a SQLite.");
          }

          this.loading = false;
        }
      );
  }


// 📌 Listar archivos almacenados en SQLite
  listSqliteFiles() {
    this.http.get<{ id: number, name: string, categoria: string }[]>('http://127.0.0.1:8000/list_sqlite_files')
      .subscribe(
        (response) => {
          this.uploadedPdfs = response.map(pdf => ({
            id: pdf.id,
            name: pdf.name,
            category: pdf.categoria // ✅ Convertimos `categoria` a `category`
          }));
        },
        (error) => {
          console.error('Error al listar archivos en SQLite:', error);
          this.uploadedPdfs = [];
        }
      );
  }

// 📌 Eliminar archivo de SQLite
  deleteSqliteFile(fileId: number) {
    this.loading = true;
    this.http.delete<{ message: string }>(`http://127.0.0.1:8000/delete_sqlite_file/${fileId}`)
      .subscribe(
        (response) => {
          alert(response.message);
          this.listSqliteFiles(); // 🔄 Recargar lista de SQLite
          this.loading = false;
        },
        (error) => {
          console.error('Error al eliminar archivo de SQLite:', error);
          this.loading = false;
        }
      );
  }


  // Crear la base de datos en Milvus
  createDatabase() {
    this.loading = true;
    this.http.post<{ message: string }>('http://127.0.0.1:8000/create_database', {})
      .subscribe(
        (response) => {
          alert(response.message);
          this.loading = false;
        },
        (error) => {
          console.error('Error al crear la base de datos:', error);
          this.loading = false;
        }
      );
  }

  // Eliminar la base de datos en Milvus y SQLite
  deleteDatabase() {
    this.loading = true;
    this.http.post<{ message: string }>('http://127.0.0.1:8000/delete_databases', {})
      .subscribe(
        (response) => {
          alert(response.message);
          // Limpieza inmediata del estado local: antes solo se vaciaba
          // uploadedPdfs y la lista de documentos indexados en Milvus seguia
          // mostrando lo ya borrado hasta recargar la pagina a mano.
          this.uploadedPdfs = [];
          this.milvusDocs = [];
          this.loading = false;
          this.listUploadedFiles();      // 🔄 carpeta de subidas
          this.listarMilvusDocuments();  // 🔄 documentos indexados
        },
        (error) => {
          console.error('Error al eliminar la base de datos:', error);
          this.loading = false;
        }
      );
  }

  // 🔄 Obtener documentos de Milvus
  listarMilvusDocuments() {
    this.loading = true;
    this.http.get<{
      documents: { document_id: string; metadata: any }[]
    }>('http://127.0.0.1:8000/milvus/list_documents')
      .subscribe({
        next: (res) => {
          this.milvusDocs = res.documents.sort((a, b) => Number(a.document_id) - Number(b.document_id));

          this.loading = false;
        },
        error: (err) => {
          console.error("❌ Error al obtener documentos de Milvus.", err);
          this.loading = false;
        }
      });
  }


// 🗑️ Eliminar un documento por ID
  deleteMilvusDocument(documentId: string) {
    if (!confirm(`¿Seguro que deseas eliminar el documento '${documentId}' de Milvus?`)) return;

    this.http.delete(`http://127.0.0.1:8000/milvus/delete_document/${documentId}`)
      .subscribe({
        next: (res: any) => {
          this.listarMilvusDocuments(); // refrescar
          alert(res.message || '✅ Documento eliminado');
        },
        error: (err) => {
          console.error('Error al eliminar documento:', err);
          alert('❌ No se pudo eliminar el documento.');
        }
      });
  }

  abrirModalEdicion(fileId: number) {
    this.http.get<any>(`http://127.0.0.1:8000/get_sqlite_file/${fileId}`).subscribe(
      (doc) => {
        this.editForm = {...doc};
        this.isEditModalOpen = true;
      },
      (error) => {
        console.error('Error al obtener documento:', error);
        alert('❌ No se pudo cargar el documento para edición.');
      }
    );
  }

  cerrarModal() {
    this.isEditModalOpen = false;
  }

  guardarCambios() {
    const formData = new FormData();
    formData.append('nombre', this.editForm.name);
    formData.append('categoria', this.editForm.categoria);
    formData.append('descripcion', this.editForm.descripcion);

    this.http.put(`http://127.0.0.1:8000/update_sqlite_file/${this.editForm.id}`, formData)
      .subscribe(
        (response: any) => {
          alert(response.message || '✅ Documento actualizado');
          this.cerrarModal();
          this.listSqliteFiles();
        },
        (error) => {
          console.error('Error al guardar cambios:', error);
          alert('❌ Error al actualizar el documento.');
        }
      );
  }

}
