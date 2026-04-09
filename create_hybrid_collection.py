"""
创建支持 BM25 + Embedding 混合搜索的 Milvus 集合
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pymilvus import MilvusClient, DataType


def create_hybrid_bm25_collection():
    """创建支持 BM25 + 向量混合搜索的集合"""

    uri = "http://localhost:19530"
    collection_name = "knowledge_base_hybrid"
    dimension = 1024  # bge-m3 embedding dimension

    client = MilvusClient(uri=uri)

    print("=" * 60)
    print(f"创建混合搜索集合: {collection_name}")
    print("=" * 60)

    # 如果集合存在，先删除
    if client.has_collection(collection_name):
        print(f"\n[警告] 集合 '{collection_name}' 已存在")
        confirm = input("确认删除并重建？(yes/no): ")
        if confirm.lower() != "yes":
            print("取消操作")
            return

        print("删除旧集合...")
        client.drop_collection(collection_name)

    # 创建 schema
    print("\n创建 schema...")

    schema = client.create_schema()
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)

    # 文本内容字段 - 启用 analyzer 用于 BM25
    schema.add_field(
        field_name="fileContent",
        datatype=DataType.VARCHAR,
        max_length=65535,
        enable_analyzer=True,  # 关键：启用分词器用于 BM25
        description="文档内容"
    )

    # 标题字段
    schema.add_field(
        field_name="formTitle",
        datatype=DataType.VARCHAR,
        max_length=512,
        description="文档标题"
    )

    # 元数据字段
    schema.add_field(field_name="document_id", datatype=DataType.VARCHAR, max_length=256)
    schema.add_field(field_name="chunk_index", datatype=DataType.INT64)

    # 密集向量字段 (embedding)
    schema.add_field(
        field_name="vector",
        datatype=DataType.FLOAT_VECTOR,
        dim=dimension,
        description="密集向量 (bge-m3 embedding)"
    )

    # 稀疏向量字段 (BM25) - 将由 BM25 函数自动生成
    from pymilvus import FunctionType
    schema.add_field(
        field_name="sparse_vector",
        datatype=DataType.SPARSE_FLOAT_VECTOR,
        description="稀疏向量 (BM25 自动生成)"
    )

    # 添加 BM25 函数 - 从 fileContent 自动生成稀疏向量
    from pymilvus import Function
    schema.add_function(
        Function(
            name="bm25_function",
            function_type=FunctionType.BM25,
            input_field_names=["fileContent"],
            output_field_names=["sparse_vector"]
        )
    )

    print(f"  - 字段: id, fileContent (analyzer), formTitle, document_id, chunk_index")
    print(f"  - 向量: vector (dense, {dimension}d)")
    print(f"  - 稀疏向量: sparse_vector (BM25 auto-generated)")
    print(f"  - BM25 函数: bm25_function")

    # 创建集合
    print(f"\n创建集合 '{collection_name}'...")
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        # 启用动态字段（可选）
        enable_dynamic_field=True
    )

    # 创建索引
    print(f"\n创建索引...")

    from pymilvus.milvus_client.index import IndexParams
    index_params = IndexParams()

    # 密集向量索引 (用于 embedding 搜索)
    index_params.add_index(
        field_name="vector",
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 128}
    )
    print(f"  - 密集向量索引: IVF_FLAT, COSINE")

    # 稀疏向量索引 (用于 BM25 搜索)
    index_params.add_index(
        field_name="sparse_vector",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
        params={"drop_ratio_build": 0.1}
    )
    print(f"  - 稀疏向量索引: SPARSE_INVERTED_INDEX, BM25")

    client.create_index(
        collection_name=collection_name,
        index_params=index_params
    )

    # 加载集合到内存
    print(f"\n加载集合到内存...")
    client.load_collection(collection_name)

    # 验证
    desc = client.describe_collection(collection_name)
    print(f"\n[OK] 集合创建成功!")
    print(f"\n最终 Schema:")
    for field in desc.get("fields", []):
        field_name = field.get("name")
        field_type = field.get("type")
        type_map = {
            1: 'BOOL', 2: 'INT8', 3: 'INT16', 4: 'INT32', 5: 'INT64',
            10: 'FLOAT', 11: 'DOUBLE', 20: 'STRING', 21: 'VARCHAR',
            23: 'ARRAY', 100: 'VECTOR_FLOAT', 101: 'VECTOR_FLOAT16',
            102: 'VECTOR_BFLOAT16', 103: 'SPARSE_FLOAT_VECTOR'
        }
        print(f"  - {field_name}: {type_map.get(field_type, field_type)}")
        if field.get("enable_analyzer"):
            print(f"    (enable_analyzer: True)")

    print(f"\n动态字段: {desc.get('enable_dynamic_field', False)}")

    # 检查函数
    if "functions" in desc:
        print(f"\n函数:")
        for func in desc.get("functions", []):
            print(f"  - {func.get('name')}: {func.get('type')}")

    print(f"\n" + "=" * 60)
    print(f"混合搜索集合已就绪!")
    print(f"集合名称: {collection_name}")
    print(f"=" * 60)

    return collection_name


if __name__ == "__main__":
    try:
        create_hybrid_bm25_collection()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
