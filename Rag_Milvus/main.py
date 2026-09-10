import uvicorn

if __name__ == "__main__":
    #uvicorn.run("asr_whisper:app", host="0.0.0.0", port=8001, reload=True)
    #uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    uvicorn.run("qa_docs:app", host="0.0.0.0", port=8000, reload=True)
