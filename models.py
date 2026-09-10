from huggingface_hub import snapshot_download
import torch

# === Paso 1: Descargar el modelo a una carpeta local
ruta_local = snapshot_download(
    repo_id="jinaai/jina-embeddings-v2-base-es",
    local_dir="jinaai/jina-embeddings-v2-base-es",
    local_dir_use_symlinks=False
)
