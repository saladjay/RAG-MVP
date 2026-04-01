# 外部知识库测试

## 正确的配置

```bash
# 端点路径
EXTERNAL_KB_BASE_URL=http://128.23.77.226:6719
EXTERNAL_KB_ENDPOINT=/cloudoa-ai/ai/file-knowledge/queryKnowledge
```

## 测试命令（PowerShell）

```powershell
# 方法1：直接使用 curl 测试
curl -X POST "http://128.23.77.226:6719/cloudoa-ai/ai/file-knowledge/queryKnowledge" `
  -H "Content-Type: application/json" `
  -d '{"query":"test","compId":"N000131","fileType":"PublicDocDispatch","searchType":1,"topk":3}'

# 方法2：使用 Python CLI（需要显式指定端点）
python -m e2e_test.cli external-kb questions/fianl_version_qa.jsonl `
  --base-url http://128.23.77.226:6719 `
  --endpoint /cloudoa-ai/ai/file-knowledge/queryKnowledge `
  --output external_kb_results.json `
  --comp-id N000131 `
  --file-type PublicDocDispatch `
  --search-type 1 `
  --topk 10 `
  --limit 3
```

## 注意事项

1. **必须显式指定 `--endpoint` 参数**，因为代码缓存可能导致默认值不生效
2. **服务返回空结果** 是正常的，表示知识库中没有匹配的文档
3. **端点路径已确认正确**：`/cloudoa-ai/ai/file-knowledge/queryKnowledge`
