from pymilvus import MilvusClient

# ====================== 改成你的局域网 Milvus 地址 ======================
MILVUS_URI = "http://192.168.xxx.xxx:19530"  
# ======================================================================

# 连接
client = MilvusClient(
    uri=MILVUS_URI
)

# 测试是否连通
print("✅ 连接成功！当前集合列表：")
print(client.list_collections())


data = [
    {"id": 1, "content": "机器学习是AI基础"},
    {"id": 2, "content": "大模型用Transformer架构"},
]

client.insert(
    collection_name="test_bm25",
    data=data
)

print("✅ 插入成功")


# 1. 先获取查询向量（调用你的本地Embedding模型）
import requests
def get_emb(text):
    r = requests.post("http://192.168.xxx.xxx:6008/embedding", json={"text": text})
    return r.json()["vector"]

query_vector = get_emb("AI 技术")

# 2. 去 Milvus 做语义搜索
res = client.search(
    collection_name="test_bm25",
    data=[query_vector],
    limit=5,
    output_fields=["id", "content"]
)

# 3. 输出结果
print("🔍 语义检索结果：")
for hit in res[0]:
    print(hit["entity"]["content"], " 得分：", hit["distance"])


res = client.search(
    collection_name="test_bm25",
    data=[],          # BM25 不需要向量
    limit=5,
    output_fields=["id", "content"],
    filter="content like '%AI%'"
)


res = client.hybrid_search(
    collection_name="test_bm25",
    dense_data=[query_vector],
    sparse_data=[],
    limit=5,
    output_fields=["id", "content"]
)