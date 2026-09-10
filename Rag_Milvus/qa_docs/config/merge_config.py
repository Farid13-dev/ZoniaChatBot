import os
import re
from omegaconf import OmegaConf


def merge_selected(config, section: str, body) -> None:
  """Fusiona la config que envia la UI SIN destruir lo que no manda.

  Dos problemas que resuelve:
  1. La UI no conoce campos como `api_base` (Groq) o `torch_dtype` (fp16).
     Con la asignacion directa `config[x]["selected"] = body.__dict__` se
     perdian en cuanto alguien pulsaba Guardar.
  2. Si el YAML referencia un secreto con ${oc.env:VAR}, la UI lo recibe ya
     resuelto y lo devolveria en claro. Aqui se detecta y se conserva la
     referencia.
  """
  incoming = {k: v for k, v in vars(body).items() if v is not None}

  previo = config.get(section, {}).get("selected", {})
  try:
    previo = OmegaConf.to_container(previo, resolve=False)
  except Exception:
    previo = dict(previo or {})

  for clave, valor_previo in (previo or {}).items():
    if isinstance(valor_previo, str) and valor_previo.startswith("${oc.env:"):
      m = re.match(r"\$\{oc\.env:([^,}]+)", valor_previo)
      var = m.group(1) if m else None
      if var and incoming.get(clave) in (os.getenv(var), "", None):
        incoming[clave] = valor_previo

  config.merge_with({section: {"selected": incoming, "provider": body.provider}})
