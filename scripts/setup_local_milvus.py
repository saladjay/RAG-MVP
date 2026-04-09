"""
本地 Milvus 数据库设置脚本

此脚本创建一个本地 Milvus Lite 数据库（嵌入式版本），
无需远程服务器，适合开发和测试。
"""

import os
import sys
from pathlib import Path


# Fix Unicode output for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def setup_local_milvus():
    """设置本地 Milvus 数据库。"""

    print("=" * 60)
    print("本地 Milvus 数据库设置")
    print("=" * 60)

    # 检查 pymilvus 是否安装
    try:
        from pymilvus import MilvusClient
        print("[OK] pymilvus 已安装")
    except ImportError:
        print("[INFO] pymilvus 未安装，正在安装...")
        os.system("uv add pymilvus")
        from pymilvus import MilvusClient

    # 创建本地数据库目录
    project_dir = Path(__file__).parent.parent
    milvus_dir = project_dir / "data" / "milvus"
    milvus_dir.mkdir(parents=True, exist_ok=True)

    db_file = milvus_dir / "local_milvus.db"
    print(f"\n数据库文件: {db_file}")

    # 创建本地 Milvus 客户端
    print("\n正在创建本地 Milvus 实例...")
    client = MilvusClient(str(db_file))
    print("[OK] 本地 Milvus 实例创建成功！")

    # 列出现有集合
    collections = client.list_collections()
    print(f"\n现有集合数量: {len(collections)}")
    if collections:
        print("现有集合:")
        for c in collections:
            print(f"  - {c}")

    # 创建测试集合
    test_collection = "test_local_kb"
    if test_collection not in collections:
        print(f"\n正在创建测试集合: {test_collection}")
        client.create_collection(
            collection_name=test_collection,
            dimension=1024,
        )
        print(f"[OK] 测试集合创建成功！")

    print("\n" + "=" * 60)
    print("本地 Milvus 设置完成！")
    print("=" * 60)
    print(f"\n使用方法:")
    print(f"  client = MilvusClient(db_file='{db_file}')")
    print(f"\n环境变量配置:")
    print(f"  MILVUS_KB_URI={db_file}")
    print(f"\n注意: 使用本地数据库时，URI 应为文件路径，不是 http:// URL")

    return str(db_file), client


def create_collection_schema(client, collection_name="knowledge_base"):
    """创建知识库集合的完整架构。"""

    from pymilvus import DataType

    print(f"\n正在创建集合: {collection_name}")

    # 检查是否已存在
    if client.has_collection(collection_name):
        print(f"集合 '{collection_name}' 已存在")
        return True

    # 定义 schema
    schema = client.create_schema()

    # 添加字段
    schema.add_field(
        field_name="id",
        datatype=DataType.INT64,
        is_primary=True,
        auto_id=True,
        description="主键（自动生成）"
    )

    schema.add_field(
        field_name="fileContent",
        datatype=DataType.VARCHAR,
        max_length=65535,
        description="文档内容"
    )

    schema.add_field(
        field_name="formTitle",
        datatype=DataType.VARCHAR,
        max_length=512,
        description="文档标题"
    )

    schema.add_field(
        field_name="document_id",
        datatype=DataType.VARCHAR,
        max_length=256,
        description="文档标识符"
    )

    schema.add_field(
        field_name="chunk_index",
        datatype=DataType.INT64,
        description="分块索引"
    )

    schema.add_field(
        field_name="vector",
        datatype=DataType.FLOAT_VECTOR,
        dim=1024,
        description="向量嵌入"
    )

    # 创建集合
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
    )

    # 创建索引
    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 128}
    }
    client.create_index(
        collection_name=collection_name,
        field_name="vector",
        index_params=index_params
    )

    print(f"[OK] 集合 '{collection_name}' 创建成功！")
    return True


def test_insert_and_query(client, collection_name="knowledge_base"):
    """测试插入和查询。"""

    import random

    print(f"\n正在测试集合 '{collection_name}'...")

    # 生成测试数据
    test_data = [
        {
            "fileContent": "这是第一段测试文本，关于人工智能技术的发展。",
            "formTitle": "测试文档1",
            "document_id": "test_doc_001",
            "chunk_index": 0,
            "vector": [random.random() for _ in range(1024)],
        },
        {
            "fileContent": "这是第二段测试文本，关于机器学习在自然语言处理中的应用。",
            "formTitle": "测试文档2",
            "document_id": "test_doc_002",
            "chunk_index": 0,
            "vector": [random.random() for _ in range(1024)],
        },
    ]

    # 插入数据
    result = client.insert(collection_name, test_data)
    print(f"[OK] 插入 {len(test_data)} 条测试数据")

    # 查询数据
    query_vector = [random.random() for _ in range(1024)]
    results = client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=2,
        output_fields=["fileContent", "formTitle", "document_id"],
    )

    print(f"[OK] 查询返回 {len(results[0])} 条结果")
    return True


def update_env_file(db_file_path):
    """更新 .env 文件以使用本地 Milvus。"""

    project_dir = Path(__file__).parent.parent
    env_file = project_dir / ".env"

    if not env_file.exists():
        print(f"\n[WARNING] .env 文件不存在于 {env_file}")
        return False

    print(f"\n正在更新 .env 文件...")

    # 读取现有内容
    with open(env_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 更新或添加 MILVUS_KB_URI
    updated = False
    new_lines = []
    uri_line = f"MILVUS_KB_URI={db_file_path}\n"

    for i, line in enumerate(lines):
        if line.startswith("MILVUS_KB_URI="):
            new_lines.append(uri_line)
            updated = True
            print(f"  更新: {line.strip()} -> {uri_line.strip()}")
        else:
            new_lines.append(line)

    if not updated:
        # 在 MILVUS 配置后添加
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("MILVUS_"):
                insert_pos = i + 1
        new_lines.insert(insert_pos, uri_line)
        print(f"  添加: {uri_line.strip()}")

    # 写回文件
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("[OK] .env 文件已更新")
    return True


if __name__ == "__main__":
    try:
        # 设置本地 Milvus
        db_file, client = setup_local_milvus()

        # 创建知识库集合
        create_collection_schema(client, "knowledge_base")

        # 测试功能
        test_insert_and_query(client, "knowledge_base")

        # 更新环境变量
        update_env_file(db_file)

        print("\n" + "=" * 60)
        print("[OK] 所有设置完成！")
        print("=" * 60)
        print(f"\n本地 Milvus 数据库已创建并配置完成。")
        print(f"现在可以重启 RAG 服务并使用批量上传功能。")

    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
