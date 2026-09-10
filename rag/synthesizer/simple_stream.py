import time
import re

class SimpleStreamResponse:
  def __init__(self, text: str, delay: float = 0.03):
    self.response_gen = self._generate(text, delay)

  def _generate(self, text: str, delay: float):
    # Divide en palabras y espacios (preservando ambos)
    for token in re.findall(r'\S+|\s+', text):
      yield token
      time.sleep(delay)
