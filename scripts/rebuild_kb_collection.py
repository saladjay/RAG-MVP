"""
重建 knowledge_base 集合，将动态字段改为固定字段

这会创建一个包含所有必需字段的正式 schema。
"""

import os
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pymilvus import MilvusClient, DataType

def rebuild_collection():
    """重建集合，使用固定字段。"""

    uri = os.getenv('MILVUS_KB_URI', 'http://128.23.74.1:19530')
    client = MilvusClient(uri=uri)

    collection_name = 'knowledge_base'

    print('=' * 60)
    print('重建 knowledge_base 集合')
    print('=' * 60)

    # 检查是否存在
    if client.has_collection(collection_name):
        # 检查是否有数据
        try:
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get('row_count', 0)
            print(f'当前集合有 {row_count} 条记录')

            if row_count > 0:
                print('[WARNING] 集合中有数据，重建将清空所有数据！')
                confirm = input('确认删除并重建？(yes/no): ')
                if confirm.lower() != 'yes':
                    print('取消操作')
                    return
        except:
            pass

        print('删除旧集合...')
        client.drop_collection(collection_name)

    # 创建新的 schema
    print('\n创建新 schema...')

    schema = client.create_schema()
    schema.add_field(field_name='id', datatype=DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(field_name='fileContent', datatype=DataType.VARCHAR, max_length=65535, description='文档内容')
    schema.add_field(field_name='formTitle', datatype=DataType.VARCHAR, max_length=512, description='文档标题')
    schema.add_field(field_name='document_id', datatype=DataType.VARCHAR, max_length=256, description='文档ID')
    schema.add_field(field_name='chunk_index', datatype=DataType.INT64, description='分块索引')
    schema.add_field(field_name='vector', datatype=DataType.FLOAT_VECTOR, dim=1024, description='向量嵌入')

    # 创建集合
    client.create_collection(collection_name=collection_name, schema=schema)
    print(f'[OK] 集合 {collection_name} 已创建')

    # 创建索引
    print('创建向量索引...')
    from pymilvus.milvus_client.index import IndexParams
    index_params = IndexParams()
    index_params.add_index(
        field_name='vector',
        index_type='IVF_FLAT',
        metric_type='COSINE',
        params={'nlist': 128}
    )

    # 注意：create_index 的调用方式因版本而异
    try:
        client.create_index(
            collection_name=collection_name,
            index_params=index_params
        )
    except Exception as e:
        print(f'[WARNING] 索引创建失败: {e}')
        print('将使用默认索引...')

    # 加载集合
    print('加载集合到内存...')
    client.load_collection(collection_name)

    # 验证 schema
    desc = client.describe_collection(collection_name)
    print('\n[OK] 集合创建成功！')
    print('\n固定字段列表:')
    for field in desc.get('fields', []):
        field_type = field.get('type')
        type_map = {
            5: 'INT64',
            21: 'VARCHAR',
            101: 'FLOAT_VECTOR',
        }
        print(f'  - {field.get("name")}: {type_map.get(field_type, field_type)}')

    print(f'\n动态字段启用: {desc.get("enable_dynamic_field", False)}')

    print('\n' + '=' * 60)
    print('[OK] 完成！现在可以重新上传文档了。')
    print('=' * 60)

if __name__ == '__main__':
    try:
        rebuild_collection()
    except Exception as e:
        print(f'\n[ERROR] {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
