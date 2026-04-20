from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok", "bot_name": "FCB Calendar Bot", "model": "qwen3:30b"}
