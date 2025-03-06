from df.enhance import enhance, init_df, load_audio, save_audio

audio_path = "asr/grabacion_w.wav"
output_path = "asr/grabacion_limpio.wav"


# Cargar el archivo de audio
#audio, sr = librosa.load(archivo_original, sr=16000, mono=True)

# Guardar el audio en formato WAV con 16kHz y mono
#sf.write(archivo_original, audio, 16000)

model, df_state, _ = init_df()  # Load default model
audio, _ = load_audio(audio_path, sr=df_state.sr())

enhanced_audio = enhance(model, df_state, audio)

save_audio(output_path, enhanced_audio, df_state.sr())
