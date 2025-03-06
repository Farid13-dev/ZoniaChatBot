# Load model directly
from transformers import AutoTokenizer, AutoModelForCausalLM

tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")
model = AutoModelForCausalLM.from_pretrained("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")
tokenizer.save_pretrained("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")
model.save_pretrained("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")
