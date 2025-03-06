from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch
import librosa
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
# load model and processor
processor = WhisperProcessor.from_pretrained("openai/whisper-medium")
model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-medium").to(device)
forced_decoder_ids = processor.get_decoder_prompt_ids(language="spanish", task="transcribe")

audio_path = "temp_audio.wav"  # Cambia esto por la ruta de tu archivo .wav
audio_sample, sampling_rate = librosa.load(audio_path, sr=16000, mono=True)

input_features = processor(audio_sample, sampling_rate=sampling_rate, return_tensors="pt").input_features.to(device)

# generate token ids
predicted_ids = model.generate(input_features, forced_decoder_ids=forced_decoder_ids)
# decode token ids to text
transcription = processor.batch_decode(predicted_ids)

transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)
print(transcription)
