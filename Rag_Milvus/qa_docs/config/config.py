# qa_docs/config/config.py
import os
import yaml
from omegaconf import OmegaConf

CONFIG_FILE = os.path.join("configuration", "config_process.yaml")


def load_config():
  if os.path.exists(CONFIG_FILE):
    return OmegaConf.load(CONFIG_FILE)
  return OmegaConf.create({})


def save_config(new_config, formatted_yaml: bool = True):
    """Guarda la configuración, opcionalmente con formato de YAML limpio."""
    if not isinstance(new_config, dict):
        # resolve=False es IMPRESCINDIBLE: con resolve=True cada guardado desde
        # la interfaz convertia ${oc.env:GROQ_API_KEY} en la clave literal y la
        # volcaba en el YAML, reintroduciendo el secreto en el repositorio.
        new_config = OmegaConf.to_container(new_config, resolve=False)

    if not formatted_yaml:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            OmegaConf.save(config=new_config, f=f)
            f.flush()
            os.fsync(f.fileno())
        return

    # Custom YAML dump (citas dobles, listas inline)
    class QuotedString(str): pass
    def quoted_presenter(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
    yaml.add_representer(QuotedString, quoted_presenter)

    if "splitter" in new_config and "selected" in new_config["splitter"]:
        selected = new_config["splitter"]["selected"]
        if "separator" in selected:
          selected["separator"] = QuotedString(selected["separator"])
        if "paragraph_separator" in selected:
          selected["paragraph_separator"] = QuotedString(selected["paragraph_separator"])
        if "backup_separators" in selected:
          selected["backup_separators"] = [QuotedString(x) for x in selected["backup_separators"]]

    class MyDumper(yaml.Dumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow=flow, indentless=False)

    def represent_list_inline(dumper, data):
        if all(isinstance(i, (str, int, float)) for i in data) and len(data) <= 10:
            return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data)

    yaml.add_representer(list, represent_list_inline, Dumper=MyDumper)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(new_config, f, Dumper=MyDumper, sort_keys=False, allow_unicode=True)

# ========== Procesamiento ==========
def get_processing_config():
    return load_config().get("processing", {})

# ========== Splitter ==========
def get_splitter_available_mode():
    return load_config().get("splitter", {}).get("available", {}).get("splitter_mode", [])

def get_splitter_available_tokenizers():
    return load_config().get("splitter", {}).get("available", {}).get("model_name_tokenizer", [])

def get_splitter_selected_config():
    return load_config().get("splitter", {}).get("selected", {})

# ========== Embedding ==========
def get_embedding_provider_name():
    return load_config().get("embedding", {}).get("provider", None)

def get_embedding_available_models():
    return load_config().get("embedding", {}).get("available", {})

def get_embedding_selected_model():
    return load_config().get("embedding", {}).get("selected", {})

# ========== Reranking ==========
def get_reranker_provider_name():
    return load_config().get("rerank", {}).get("provider", None)

def get_reranker_available_models():
    return load_config().get("rerank", {}).get("available", {})

def get_reranker_selected_model():
    return load_config().get("rerank", {}).get("selected", {})

# ========== LLM ==========
def get_llm_provider_name():
    return load_config().get("llm", {}).get("provider", None)

def get_llm_available_models():
    return load_config().get("llm", {}).get("available", {})

def get_llm_selected_model():
    return load_config().get("llm", {}).get("selected", {})

# ========== Retriever ==========
def get_retriever_config():
    return load_config().get("retriever", {})

# ========== Response Config ==========
def get_response_config():
    return load_config().get("response_config", {})

# ========== Directory Reader ==========
def get_directory_reader_config():
    return load_config().get("directory_reader", {})

# ========== Question Gen ==========
def get_question_gen_config():
    return load_config().get("question_gen", {})

# ========== General Config ==========
def get_general_config():
    return load_config().get("general_config", {})
