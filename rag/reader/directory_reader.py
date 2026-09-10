"""Simple reader that reads files of different formats from a directory."""
import asyncio
import logging
import mimetypes
import multiprocessing
import os
import warnings
from datetime import datetime
from functools import reduce
from itertools import repeat
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Type

from tqdm import tqdm

from rag.node.base_node import Document
from rag.reader.base_reader import BaseReader
from .file.pdf import PyPDFReader as PDFReader
from .file.docx import DocxReader
from .file.txt import TxtReader

DEFAULT_FILE_READER_CLS: Dict[str, Type[BaseReader]] = {  # type: ignore
  ".pdf": PDFReader,
  ".docx": DocxReader,
  ".txt": TxtReader,
}

import fitz  # PyMuPDF


def default_file_metadata_func(file_path: str) -> Dict:
  """Extrae metadatos del sistema de archivos y metadatos internos del PDF."""

  base_metadata = {
    "file_path": file_path,
    "file_name": os.path.basename(file_path),
    "file_type": mimetypes.guess_type(file_path)[0],
    "file_size": os.path.getsize(file_path),
    "creation_date": datetime.fromtimestamp(Path(file_path).stat().st_ctime).strftime("%Y-%m-%d"),
    "last_modified_date": datetime.fromtimestamp(Path(file_path).stat().st_mtime).strftime("%Y-%m-%d"),
    "last_accessed_date": datetime.fromtimestamp(Path(file_path).stat().st_atime).strftime("%Y-%m-%d"),
  }

  # 🔍 Si es PDF, extraemos metadata del documento
  if file_path.lower().endswith(".pdf"):
    try:
      doc = fitz.open(file_path)
      pdf_meta = doc.metadata  # Diccionario: title, author, etc.

      # ✅ Campos típicos útiles
      base_metadata["title"] = pdf_meta.get("title")
      base_metadata["Author"] = pdf_meta.get("author")
      base_metadata["Creator"] = pdf_meta.get("creator")
      base_metadata["Producer"] = pdf_meta.get("producer")
      base_metadata["ModDate"] = pdf_meta.get("modDate")
      base_metadata["CreationDate"] = pdf_meta.get("creationDate")

      # También puedes agregar número total de páginas:
      base_metadata["total_pages"] = doc.page_count


    except Exception as e:
      print(f"⚠️ No se pudieron leer metadatos internos del PDF: {file_path} - {e}")

  return base_metadata


logger = logging.getLogger(__name__)


class DirectoryReader(BaseReader):
  """Simple directory reader.

  Load files from file directory.
  Automatically select the best file reader given file extensions.

  Args:
      input_dir (str): Path to the directory.
      input_files (List): List of file paths to read
          (Optional; overrides input_dir, exclude)
      exclude (List): glob of python file paths to exclude (Optional)
      exclude_hidden (bool): Whether to exclude hidden files (dotfiles).
      encoding (str): Encoding of the files.
          Default is utf-8.
      errors (str): how encoding and decoding errors are to be handled,
            see https://docs.python.org/3/library/functions.html#open
      recursive (bool): Whether to recursively search in subdirectories.
          False by default.
      filename_as_id (bool): Whether to use the filename as the document id.
          False by default.
      required_exts (Optional[List[str]]): List of required extensions.
          Default is None.
      file_extractor (Optional[Dict[str, BaseReader]]): A mapping of file
          extension to a BaseReader class that specifies how to convert that file
          to text. If not specified, use default from DEFAULT_FILE_READER_CLS.
      num_files_limit (Optional[int]): Maximum number of files to read.
          Default is None.
      file_metadata (Optional[Callable[str, Dict]]): A function that takes
          in a filename and returns a Dict of metadata for the Document.
          Default is None.
  """

  supported_suffix = list(DEFAULT_FILE_READER_CLS.keys())

  def __init__(
    self,
    input_dir: Optional[str] = None,
    input_files: Optional[List] = None,
    exclude: Optional[List] = None,
    exclude_hidden: bool = True,
    errors: str = "ignore",
    recursive: bool = False,
    encoding: str = "utf-8",
    filename_as_id: bool = False,
    required_exts: Optional[List[str]] = None,
    file_extractor: Optional[Dict[str, BaseReader]] = None,
    num_files_limit: Optional[int] = None,
    file_metadata: Optional[Callable[[str], Dict]] = None,
    concat_pages: bool = False,
  ) -> None:
    """Initialize with parameters."""
    super().__init__()

    if not input_dir and not input_files:
      raise ValueError("Must provide either `input_dir` or `input_files`.")

    self.errors = errors
    self.encoding = encoding

    self.exclude = exclude
    self.recursive = recursive
    self.exclude_hidden = exclude_hidden
    self.required_exts = required_exts
    self.num_files_limit = num_files_limit
    self.concat_pages = concat_pages

    if input_files:
      self.input_files = []
      for path in input_files:
        if not os.path.isfile(path):
          raise ValueError(f"File {path} does not exist.")
        input_file = Path(path)
        self.input_files.append(input_file)
    elif input_dir:
      if not os.path.isdir(input_dir):
        raise ValueError(f"Directory {input_dir} does not exist.")
      self.input_dir = Path(input_dir)
      self.exclude = exclude
      self.input_files = self._add_files(self.input_dir)

    if file_extractor is not None:
      self.file_extractor = file_extractor
    else:
      self.file_extractor = {}

    self.file_metadata = file_metadata or default_file_metadata_func
    self.filename_as_id = filename_as_id

  def is_hidden(self, path: Path) -> bool:
    return any(
      part.startswith(".") and part not in [".", ".."] for part in path.parts
    )

  def _add_files(self, input_dir: Path) -> List[Path]:
    """Add files."""
    all_files = set()
    rejected_files = set()

    if self.exclude is not None:
      for excluded_pattern in self.exclude:
        if self.recursive:
          # Recursive glob
          for file in input_dir.rglob(excluded_pattern):
            rejected_files.add(Path(file))
        else:
          # Non-recursive glob
          for file in input_dir.glob(excluded_pattern):
            rejected_files.add(Path(file))

    file_refs: Generator[Path, None, None]
    if self.recursive:
      file_refs = Path(input_dir).rglob("*")
    else:
      file_refs = Path(input_dir).glob("*")

    for ref in file_refs:
      # Manually check if file is hidden or directory instead of
      # in glob for backwards compatibility.
      is_dir = ref.is_dir()
      skip_because_hidden = self.exclude_hidden and self.is_hidden(ref)
      skip_because_bad_ext = (
        self.required_exts is not None and ref.suffix not in self.required_exts
      )
      skip_because_excluded = ref in rejected_files

      if (
        is_dir
        or skip_because_hidden
        or skip_because_bad_ext
        or skip_because_excluded
      ):
        continue
      else:
        all_files.add(ref)

    new_input_files = sorted(all_files)

    if len(new_input_files) == 0:
      raise ValueError(f"No files found in {input_dir}.")

    if self.num_files_limit is not None and self.num_files_limit > 0:
      new_input_files = new_input_files[0: self.num_files_limit]

    # print total number of files added
    logger.debug(
      f"> [DirectoryReader] Total files added: {len(new_input_files)}"
    )

    return new_input_files

  def _exclude_metadata(self, documents: List[Document]) -> List[Document]:
    """Exclude metadata from documents.

    Args:
        documents (List[Document]): List of documents.
    """
    for doc in documents:
      # Keep only metadata['file_path'] in both embedding and llm content
      # str, which contain extreme important context that about the chunks.
      # Dates is provided for convenience of postprocessor such as
      # TimeWeightedPostprocessor, but excluded for embedding and LLMprompts
      doc.excluded_embed_metadata_keys.extend(
        [
          "file_name",
          "file_type",
          "file_size",
          "creation_date",
          "last_modified_date",
          "last_accessed_date",
        ]
      )
      doc.excluded_llm_metadata_keys.extend(
        [
          "file_name",
          "file_type",
          "file_size",
          "creation_date",
          "last_modified_date",
          "last_accessed_date",
        ]
      )

    return documents

  @staticmethod
  def load_file(
    input_file: Path,
    file_metadata: Callable[[str], Dict],
    file_extractor: Dict[str, BaseReader],
    filename_as_id: bool = False,
    encoding: str = "utf-8",
    errors: str = "ignore",
    *,
    concat_pages: bool = False,  # ← acepta flag
  ) -> List[Document]:
    """Carga un archivo y, si es PDF y concat_pages=True,
    devuelve un solo Document con todas las páginas unidas."""
    metadata: Optional[dict] = None
    documents: List[Document] = []

    if file_metadata is not None:
      metadata = file_metadata(str(input_file))

    file_suffix = input_file.suffix.lower()
    if (
      file_suffix in DirectoryReader.supported_suffix
      or file_suffix in file_extractor
    ):
      # — 1. obtener el reader adecuado —
      if file_suffix not in file_extractor:
        reader_cls = DEFAULT_FILE_READER_CLS[file_suffix]
        file_extractor[file_suffix] = reader_cls()
      reader = file_extractor[file_suffix]

      # — 2. cargar el archivo (puede devolver varias páginas) —
      try:
        docs = reader.load_data(input_file, extra_info=metadata)
      except ImportError as e:
        raise
      except Exception as e:
        print(f"Failed to load file {input_file}: {e}. Skipping…", flush=True)
        return []

      # — 3. UNIR páginas si se trata de un PDF y el flag está activo —
      if file_suffix == ".pdf" and concat_pages and len(docs) > 1:
        # Al unir las paginas se perdia num_page: merged_meta copiaba el de
        # docs[0] (pagina 0) para TODO el documento, y las fuentes que veia
        # el usuario apuntaban siempre a la pagina 0. Guardamos en que
        # caracter empieza cada pagina para recuperarlo chunk a chunk.
        SEP = chr(10) * 2
        page_map, pos = [], 0
        for idx, d in enumerate(docs):
          page_map.append([pos, (d.metadata or {}).get("num_page", idx)])
          pos += len(d.text) + len(SEP)
        full_text = SEP.join(d.text for d in docs)
        merged_meta = {**(docs[0].metadata or {}), **(metadata or {})}
        merged_meta["_page_map"] = page_map
        merged_meta.pop("num_page", None)   # se calcula por chunk al indexar
        merged = Document(text=full_text, metadata=merged_meta)
        # Fuera del texto que se embebe y del prompt del LLM.
        for _attr in ("excluded_embed_metadata_keys", "excluded_llm_metadata_keys"):
          try:
            getattr(merged, _attr).append("_page_map")
          except Exception:
            pass
        docs = [merged]

      documents.extend(docs)

    else:
      # lectura estándar de txt, etc.
      with open(input_file, errors=errors, encoding=encoding) as f:
        data = f.read()
      if data:
        doc = Document(text=data, metadata=metadata or {})
        if filename_as_id:
          doc.id_ = str(input_file)
        documents.append(doc)

    return documents

  def load_data(
    self, show_progress: bool = False, num_workers: Optional[int] = None
  ) -> List[Document]:

    documents: List[Document] = []
    files_to_process = self.input_files

    if num_workers and num_workers > 1:
      with multiprocessing.Pool(num_workers) as p:
        results = p.starmap(
          DirectoryReader.load_file,
          zip(
            files_to_process,
            repeat(self.file_metadata),
            repeat(self.file_extractor),
            repeat(self.filename_as_id),
            repeat(self.encoding),
            repeat(self.errors),
            repeat(self.concat_pages),  # ← pasa flag
          ),
        )
        documents = reduce(lambda x, y: x + y, results)
    else:
      if show_progress:
        files_to_process = tqdm(files_to_process, desc="Loading files")

      for input_file in files_to_process:
        documents.extend(
          DirectoryReader.load_file(
            input_file=input_file,
            file_metadata=self.file_metadata,
            file_extractor=self.file_extractor,
            filename_as_id=self.filename_as_id,
            encoding=self.encoding,
            errors=self.errors,
            concat_pages=self.concat_pages,  # ← pasa flag
          )
        )

    return self._exclude_metadata(documents)

  async def load_data_async(self, show_progress: bool = False, num_workers: Optional[int] = None):
    """Versión asíncrona de load_data usando asyncio.to_thread"""
    return await asyncio.to_thread(self.load_data, show_progress, num_workers)

  def iter_data(
    self, show_progress: bool = False
  ) -> Generator[List[Document], Any, Any]:
    """Load data iteratively from the input directory.

    Args:
        show_progress (bool): Whether to show tqdm progress bars. Defaults to False.

    Returns:
        Generator[List[Document]]: A list of documents.
    """
    files_to_process = self.input_files

    if show_progress:
      files_to_process = tqdm(self.input_files, desc="Loading files", unit="file")

    for input_file in files_to_process:
      documents = DirectoryReader.load_file(
        input_file=input_file,
        file_metadata=self.file_metadata,
        file_extractor=self.file_extractor,
        filename_as_id=self.filename_as_id,
        encoding=self.encoding,
        errors=self.errors,
      )

      documents = self._exclude_metadata(documents)

      if len(documents) > 0:
        yield documents
