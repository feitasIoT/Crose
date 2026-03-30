from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
import uvicorn

app = FastAPI()
# 第一次启动会自动下载，建议挂载目录持久化模型
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/embed")
async def get_embedding(data: dict):
    text = data.get("text", "")
    vector = model.encode(text).tolist()
    return {"vector": vector}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
