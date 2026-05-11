"""
RAG（检索增强生成）核心
1. 读取知识库文档
2. 切片 + 向量化 + 存入 ChromaDB
3. 提供搜索接口
"""
import os
import chromadb
from sentence_transformers import SentenceTransformer

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
KNOWLEDGE_DIR = "knowledge_base"
DB_DIR = "chroma_db"
CHUNK_SIZE = 150

# 模型和数据库只加载一次，所有调用共享
_model = None
_collection = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=DB_DIR)
        _collection = client.get_collection("knowledge")
    return _collection


def load_documents(directory: str) -> list[dict]:
    """读取目录下所有 .txt 文件，返回 [{filename, content}]"""
    docs = []
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            path = os.path.join(directory, filename)
            with open(path, "r", encoding="utf-8") as f:
                docs.append({"filename": filename, "content": f.read()})
    return docs


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """按段落切片，太长再按字数切"""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) <= chunk_size:
            current += para + " "
        else:
            if current:
                chunks.append(current.strip())
            current = para + " "
    if current:
        chunks.append(current.strip())
    return chunks


def build_knowledge_base():
    """读文档 → 切片 → 向量化 → 存 ChromaDB"""
    print("加载 Embedding 模型...")
    model = _get_model()

    print("初始化向量数据库...")
    client = chromadb.PersistentClient(path=DB_DIR)

    # 每次重建（生产环境应做增量更新）
    try:
        client.delete_collection("knowledge")
    except Exception:
        pass
    collection = client.create_collection(
        "knowledge",
        metadata={"hnsw:space": "cosine"}  # 余弦距离，范围[0,2]，0=完全相同
    )

    print("读取并处理文档...")
    docs = load_documents(KNOWLEDGE_DIR)
    all_chunks, all_ids, all_metadata = [], [], []

    for doc in docs:
        chunks = split_into_chunks(doc["content"])
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"{doc['filename']}_{i}")
            all_metadata.append({"source": doc["filename"]})

    print(f"向量化 {len(all_chunks)} 个文本块...")
    embeddings = model.encode(all_chunks).tolist()

    collection.add(
        documents=all_chunks,
        embeddings=embeddings,
        ids=all_ids,
        metadatas=all_metadata,
    )
    print(f"知识库构建完成：{len(all_chunks)} 个文本块")


SIMILARITY_THRESHOLD = 0.5  # 余弦距离阈值，超过此值丢弃（距离越小越相似）


def search_knowledge(query: str, top_k: int = 3) -> str:
    """搜索知识库，返回最相关的 top_k 段文字"""
    collection = _get_collection()
    query_embedding = _get_model().encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]
    sources = [m["source"] for m in results["metadatas"][0]]
    distances = results["distances"][0]  # 距离越小越相似

    output = []
    for doc, source, dist in zip(docs, sources, distances):
        if dist <= SIMILARITY_THRESHOLD:  # 余弦距离越小越相似
            output.append(f"[来源: {source}]\n{doc}")

    if not output:
        return "知识库中没有找到相关内容。"
    return "\n\n".join(output)


if __name__ == "__main__":
    # 直接运行此文件 = 构建知识库
    build_knowledge_base()

    # 测试搜索
    print("\n--- 测试搜索 ---")
    print(search_knowledge("我想退货怎么办"))
    print("\n---")
    print(search_knowledge("什么是Transformer"))
