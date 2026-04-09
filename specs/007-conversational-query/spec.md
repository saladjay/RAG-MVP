# Feature Specification: Conversational Query Enhancement

**Feature Branch**: `007-conversational-query`
**Created**: 2026-04-09
**Status**: Draft
**Input**: User description: "我还需要一个多轮对话功能，需要保留多轮对话，引导用户给出更多信息，让query改写模块的llm处理多轮对话功能。D:\project\OA\发文(2)\2024 这个文件夹里还需要汇总公文内容的类型，并且进行联想，扩充口语化表达和同义词表达。我希望你帮我思考一下如何在进入query检索之前做得更好"

## Clarifications

### Session 2026-04-09

- Q: Multi-turn conversation session timeout duration? → A: 15 minutes with 10-turn limit per session
- Q: System availability target? → A: 99.5% (standard enterprise application, single-instance with simple failure recovery)
- Q: Observability requirements? → A: Full tracing (structured JSON logging + trace_id propagation + Langfuse integration)
- Q: Session state storage mechanism? → A: Redis for fast access with automatic TTL expiration

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversational Information Gathering (Priority: P1)

A user starts with a vague query like "我想找关于安全的规定" (I want to find regulations about safety). Instead of immediately searching, the system engages in a conversation to gather missing information:

1. System: "请问您需要查找哪一年的安全规定？"
2. User: "去年的"
3. System: "2024年有以下安全相关的规定：安全生产管理办法、消防管理规定、应急预案等。请问您具体需要哪方面的？"
4. User: "消防相关的"
5. System: "好的，让我为您搜索2024年消防相关的规定文件。"

The conversation history is preserved and the final search includes all gathered context.

**Why this priority**: This is the core capability - multi-turn dialogue significantly improves query quality by progressively gathering information through natural conversation.

**Independent Test**: Can be fully tested by initiating conversations with incomplete queries and verifying that the system correctly asks follow-up questions and builds context.

**Acceptance Scenarios**:

1. **Given** a user submits "我想找关于安全的规定", **When** the system processes the query, **Then** it should identify missing year and specific topic dimensions and initiate a conversational flow
2. **Given** the system asks for year and user responds "去年的", **When** the system interprets the response, **Then** it should convert "去年的" to "2024年" and continue gathering information
3. **Given** the system has gathered year and topic information, **When** it proceeds to search, **Then** the final query should include "2024年" and "消防相关" context
4. **Given** a user provides inconsistent information across turns, **When** the system detects the inconsistency, **Then** it should ask for clarification

---

### User Story 2 - Colloquial Expression Recognition (Priority: P1)

A user uses informal or colloquial language that differs from official document terminology:

- User says: "有没有关于防火的规定" (Are there regulations about fire prevention?)
- System recognizes: "防火" → "消防" (fire prevention → fire protection)
- User says: "我要找去年发的关于大家加班的文件" (I want to find the file sent last year about everyone working overtime)
- System recognizes: "加班" → "劳动节假日安排" or "值班工作" (overtime → holiday arrangements or duty work)

The system maintains a mapping of colloquial terms to formal document terminology and uses this to understand user intent.

**Why this priority**: Users naturally use informal language. Mapping colloquial expressions to formal terminology is essential for accurate retrieval.

**Independent Test**: Can be tested by submitting queries with colloquial terms and verifying that the system correctly translates them to formal terminology.

**Acceptance Scenarios**:

1. **Given** a user submits "有没有关于防火的规定", **When** the system processes the query, **Then** it should map "防火" to "消防" and search for fire protection regulations
2. **Given** a user submits "我要找关于开会的文件" (I want to find files about meetings), **When** the system processes the query, **Then** it should map to "会议通知" or "会议纪要" (meeting notices or minutes)
3. **Given** a user submits "有没有关于涨工资的文件" (Are there files about salary increases?), **When** the system processes the query, **Then** it should map to relevant terms like "超额利润分享" or "薪酬福利" (excess profit sharing or compensation benefits)
4. **Given** a user submits a query with an unmapped colloquial term, **When** the system processes the query, **Then** it should attempt to find similar terms or ask for clarification

---

### User Story 3 - Synonym and Related Term Expansion (Priority: P2)

When a user searches for a concept, the system automatically expands the query with related terms to improve recall:

- User says: "关于党建的文件" (Files about party building)
- System expands to include: "党风廉政" (party conduct and integrity), "党纪学习教育" (party discipline education), "党员大会" (party member meeting), etc.

The system uses a knowledge graph of related concepts based on document content analysis to enhance search comprehensiveness.

**Why this priority**: Synonym expansion improves search recall by finding documents that use different terminology for the same concept.

**Independent Test**: Can be tested by submitting queries and verifying that related terms are included in the search.

**Acceptance Scenarios**:

1. **Given** a user submits "关于党建的文件", **When** the system processes the query, **Then** it should expand the search to include related terms like "党风廉政", "党纪学习教育", "党员大会"
2. **Given** a user submits "关于人事的文件" (Files about personnel), **When** the system processes the query, **Then** it should expand to include "任免" (appointments and removals), "选举" (elections), "评优" (excellence evaluation)
3. **Given** a user submits "关于安全的文件", **When** the system processes the query, **Then** it should expand to include "安全生产", "消防", "应急预案", "防汛" (safety production, fire protection, emergency plans, flood prevention)
4. **Given** a user submits a specific query that doesn't need expansion, **When** the system processes the query, **Then** it should not over-expand and dilute the search results

---

### User Story 4 - Conversation Context Persistence (Priority: P1)

A user engages in a multi-turn conversation that spans several minutes:

1. User: "我想找关于安全生产的文件"
2. System: "请问您需要查找哪一年的安全生产文件？"
3. User: "2024年的"
4. [User asks about something else in another session]
5. User: "还有关于消防的呢？" (What about fire protection ones?)
6. System: Remembers the context from earlier and searches for "2024年消防相关" files

The conversation context is preserved across turns, allowing the system to reference previously gathered information.

**Why this priority**: Context persistence is fundamental to natural multi-turn dialogue. Without it, each turn would be independent and conversational flow would be broken.

**Independent Test**: Can be tested by engaging in multi-turn conversations and verifying that context is maintained across turns.

**Acceptance Scenarios**:

1. **Given** a user has established "2024年" context in previous turns, **When** the user asks a follow-up question without specifying year, **Then** the system should use the previously established year context
2. **Given** a user has established "工会" (labor union) context, **When** the user asks "有没有关于开会的" (Are there any about meetings?), **Then** the system should interpret as "工会会议" (union meetings)
3. **Given** a conversation spans multiple sessions, **When** a user returns after a period of inactivity, **Then** the system should optionally summarize previous context or start fresh based on user preference
4. **Given** a user explicitly starts a new topic, **When** the system detects the topic change, **Then** it should clear irrelevant context while preserving relevant information

---

### User Story 5 - Proactive Query Improvement Suggestions (Priority: P2)

Before executing a search, the system analyzes the query and suggests improvements:

User submits: "关于开会"

System responds:
"您的查询可以更具体。我发现以下相关内容：
- 2024年有3份会议通知（党总支、工会、职工代表大会）
- 2024年有2份会议纪要（安全生产、龙舟水防护）
请问您需要查找哪一种？"

The user can then choose a specific option or continue with the broader search.

**Why this priority**: Proactive suggestions guide users toward more effective queries without requiring explicit prompting.

**Independent Test**: Can be tested by submitting vague queries and verifying that helpful suggestions are provided.

**Acceptance Scenarios**:

1. **Given** a user submits "关于开会", **When** the system analyzes available documents, **Then** it should suggest specific meeting types with counts
2. **Given** a user submits "关于制度", **When** the system analyzes available documents, **Then** it should suggest specific regulation types (办法、细则、规定) available
3. **Given** a user submits a query that matches many documents, **When** the system provides suggestions, **Then** it should offer filtering options by dimension (year, organization, type)
4. **Given** a user selects a suggestion, **When** the system processes the selection, **Then** it should execute the refined query

---

### User Story 6 - Structured Query Extraction and Classification (Priority: P1)

The system performs structured extraction of query elements and classifies the query type to determine the appropriate response strategy. Each user input is analyzed to produce a structured output containing:

**Extracted Elements**:
- **Temporal**: Year (2024), date (完整日期), time_range (近三年/去年/上半年), relative_time (今年/本月)
- **Spatial**: Organization (粤东科/党总支/工会), location_type (公司级/部门级)
- **Document**: doc_type (通知/通报/报告/请示/纪要), doc_number (文号)
- **Knowledge Base**: company_id (e.g., N000002), file_type (PublicDocDispatch/PublicDocReceive)
- **Content**: topic_keywords (主题关键词), policy_names (完整制度名称)

**Classification**:
- **Topic Class**: meta_info (询问文档本身) | business_query (询问文档内容) | unknown
- **Is Follow-up**: Detects pronouns (这/那/那个/它) referencing previous context
- **Confidence**: high | medium | low based on extraction clarity

**Query Type Examples**:

*Meta-info queries* (asking about documents themselves):
- "2024年发布了多少个制度" → year:2024, has_count_query:true, topic:制度发布
- "有没有关于安全的制度目录" → keyword:制度+目录, topic_class:meta_info
- "去年的制度有没有更新版本" → temporal:去年, keyword:版本更新

*Business queries* (asking about document content):
- "经理级别的住宿标准是多少" → level:经理, keyword:住宿标准, quantifier:多少
- "关于安全生产的要求是什么" → keyword:安全生产+要求
- "能不能报销交通费用" → keyword:可以报销+交通

*Follow-up queries*:
- "上海的呢" (context: previously asked about Beijing) → is_follow_up:true, inherit:上海
- "那消防的呢" (context: previously asked about safety) → is_follow_up:true, keyword:消防

**Why this priority**: Structured extraction and classification enables the system to understand user intent precisely and route queries to the appropriate processing logic. It's the foundation for all other conversational capabilities.

**Independent Test**: Can be tested by submitting various query types and verifying the structured output matches expected extraction and classification.

**Acceptance Scenarios**:

1. **Given** a user submits "2024年发布了多少个制度", **When** the system extracts and classifies, **Then** it should output: temporal.year:[2024], quantity.has_count_query:true, entities.keywords:[制度,发布], classification.topic_class:meta_info
2. **Given** a user submits "经理级别的住宿标准是多少", **When** the system extracts and classifies, **Then** it should output: person.level:[经理], entities.keywords:[住宿,标准], quantity.quantifiers:[多少], classification.topic_class:business_query
3. **Given** a user submits "上海的呢" after asking about Beijing, **When** the system extracts and classifies, **Then** it should output: spatial.organization:[上海], classification.is_follow_up:true, entities.keywords:inherited_from_previous_turn
4. **Given** a user submits an ambiguous query, **When** the system extracts and classifies, **Then** classification.confidence should be "medium" or "low" and trigger clarification prompts

---

---

### User Story 7 - Business Domain Classification and Routing (Priority: P1)

After extracting structured elements from a user query, the system classifies the query into a business domain to enable intelligent routing and specialized handling:

**Domain Classification Examples**:

- User: "关于差旅住宿报销的规定" → business_domain: "finance", sub_domain: "accommodation"
- User: "有没有关于绩效考核的文件" → business_domain: "hr", sub_domain: ""
- User: "安全生产管理的办法" → business_domain: "safety", sub_domain: ""
- User: "党建工作的相关文件" → business_domain: "party", sub_domain: ""
- User: "档案管理规定" → business_domain: "archive", sub_domain: ""

The system uses keyword-based classification with priority ordering to determine the appropriate business domain, enabling:

1. **Specialized Knowledge Bases**: Route queries to domain-specific document collections
2. **Domain-Specific Prompts**: Use different prompt templates for different business areas
3. **Expert Routing**: Route complex queries to domain specialists when needed
4. **Analytics**: Track query patterns by business domain for insights

**Why this priority**: Business domain classification is essential for routing queries to the appropriate knowledge base and processing logic. It enables specialization and improves retrieval accuracy by narrowing the search scope to relevant documents.

**Independent Test**: Can be tested by submitting queries from different business domains and verifying correct classification and routing.

**Acceptance Scenarios**:

1. **Given** a user submits "关于差旅费报销的标准", **When** the system classifies the query, **Then** it should output: business_domain:"finance", sub_domain:""
2. **Given** a user submits "住宿费能报多少", **When** the system classifies the query, **Then** it should output: business_domain:"finance", sub_domain:"accommodation"
3. **Given** a user submits "员工绩效考核办法", **When** the system classifies the query, **Then** it should output: business_domain:"hr", sub_domain:""
4. **Given** a user submits "安全生产应急预案", **When** the system classifies the query, **Then** it should output: business_domain:"safety", sub_domain:""
5. **Given** a user submits a query spanning multiple domains, **When** the system classifies, **Then** it should use priority ordering and select the highest priority domain

---

---

### User Story 8 - Structured Query Generation for Retrieval (Priority: P1)

After all extraction, classification, and domain routing, the system generates three independent search queries optimized for document retrieval:

**Generated Output Structure**:
```json
{
  "q1": "First search question variation",
  "q2": "Second search question variation",
  "q3": "Third search question variation",
  "must_include": "required terms, 3-6 items",
  "keywords": "expanded keywords with synonyms, 5-10 items"
}
```

**Query Generation by Domain**:

*Business Query Domain* (finance/hr/safety/etc.):
- Generates questions incorporating collected slots: city, expense_type, level, topic
- Uses topic-specific templates: standard ("标准是多少"), rule ("需要哪些单据"), process ("流程是什么"), scope ("是否可以报销")
- Adds location context: city name or province_relation (省内/省外/跨省/全国)
- Expands expense_type colloquial terms: "住宿/酒店", "餐饮/餐补", "交通/打车/高铁"

*Meta Info Domain* (document inventory queries):
- Generates questions for different subtypes: directory, count, search, version, effective_date, responsibility, templates, definitions
- Uses domain-specific question patterns without forcing unrelated terms like "报销/出差"

*Unknown Domain*:
- Performs neutral rewriting of user input with light structuring
- Avoids introducing domain-specific terms not present in original query

**Example Outputs**:

User: "北京的住宿标准是多少"
```json
{
  "q1": "北京住宿费报销标准是多少",
  "q2": "北京住宿费用上限是多少",
  "q3": "北京经理级住宿标准如何规定",
  "must_include": "报销, 住宿, 标准, 北京",
  "keywords": "报销, 住宿/酒店, 标准, 上限/额度, 北京, 凭证/单据"
}
```

User: "公司有多少个制度"
```json
{
  "q1": "公司共有多少份制度",
  "q2": "现行有效制度数量是多少",
  "q3": "目前制度总数是多少",
  "must_include": "制度, 数量/总数",
  "keywords": "制度, 数量/统计, 总数, 有效/现行"
}
```

**Why this priority**: This is the final output layer that converts all previous analysis into actual search queries. The three-question variation approach improves retrieval recall by capturing different phrasings and perspectives.

**Independent Test**: Can be tested by submitting queries and verifying the generated output contains appropriate question variations and keyword expansions.

**Acceptance Scenarios**:

1. **Given** a user submits "北京的住宿标准是多少", **When** the system generates retrieval queries, **Then** it should output three question variations with must_include containing "报销, 住宿, 标准, 北京"
2. **Given** a user submits "关于安全生产的制度有哪些", **When** the system generates retrieval queries, **Then** it should output questions about safety production regulations without forcing finance terms like "报销"
3. **Given** a user submits "怎么查制度", **When** the system generates retrieval queries, **Then** it should output search-related questions with keywords like "检索/搜索/关键词"
4. **Given** a collected slot contains city="上海" and expense_type="交通", **When** the system generates questions, **Then** all three questions should explicitly include "上海" and "交通/交通费"

---

### Edge Cases

- What happens when a user changes topics mid-conversation without explicitly signaling?
- How does the system handle ambiguous pronouns like "那个" (that one) or "它" (it) that reference previous context?
- What happens when a user provides contradictory information across conversation turns?
- How does the system handle colloquial terms that have multiple possible meanings?
- What happens when conversation history becomes very long (20+ turns)?
- How does the system handle when no documents match the gathered criteria?
- What happens when a user provides information that doesn't match any document dimension?
- How does the system handle time expressions like "上周" (last week), "最近" (recently), "去年年底" (end of last year)?
- What happens when keywords match multiple business domains?
- How does the system handle queries that don't match any defined business domain?
- What happens when collected slots are empty but query type is known?
- How does the system prevent forcing domain-specific terms (e.g., "报销") into unrelated domain queries?

## Requirements *(mandatory)*

### Functional Requirements

**Structured Query Extraction and Classification**:
- **FR-001**: System MUST perform structured extraction of query elements in the following categories:
  - **Temporal**: year (四位数年份), date (完整日期), time_range (近三年/去年/上半年), relative_time (今年/本月/去年/年底)
  - **Spatial**: organization (粤东科/党总支/工会/各党支部), location_type (公司级/部门级/多部门)
  - **Document**: doc_type (通知/通报/报告/请示/纪要/公示/方案/办法/细则/规则/规划/要点), doc_number (文号格式)
  - **Knowledge Base**: company_id (provided by external system), file_type (PublicDocDispatch/发文, PublicDocReceive/收文)
  - **Content**: topic_keywords (主题关键词), policy_names (完整制度名称)
  - **Quantity**: has_count_query (含"多少/几个/总数"→true), numbers (明确数字), quantifiers (多少/几个/若干)
- **FR-001A**: When file_type (发文/收文) can be determined from query context, system MUST route to the specific knowledge base
- **FR-001B**: When file_type (发文/收文) cannot be determined from query context, system MUST search both knowledge bases (PublicDocDispatch and PublicDocReceive) simultaneously to ensure comprehensive results
- **FR-001C**: Company ID is provided by external system and used as context parameter for all search operations
- **FR-002**: System MUST classify each query into one of three topic classes:
  - **meta_info**: Queries about documents themselves (count, list, directory, version, update, template)
  - **business_query**: Queries about document content (standards, requirements, processes, scope)
  - **unknown**: Unclear intent that requires clarification
- **FR-003**: System MUST detect follow-up queries by identifying pronouns (这/那/这个/那个/它/上述/前面) and referencing conversation history
- **FR-004**: System MUST assign confidence scores (high/medium/low) based on extraction clarity and completeness
- **FR-005**: System MUST support keyword inheritance from previous turns when current turn lacks explicit keywords

**Conversation Context Management**:
- **FR-006**: System MUST maintain conversation history across multiple turns of dialogue
- **FR-007**: System MUST extract and preserve query dimensions from each conversation turn
- **FR-008**: System MUST identify when conversation context should be cleared vs. preserved (topic change detection)
- **FR-009**: System MUST maintain conversation session state with appropriate timeout/expiration
- **FR-010**: System MUST support follow-up questions that reference previous context (pronouns, implied topics)
- **FR-010A**: System MUST enforce a session timeout of 15 minutes of inactivity
- **FR-010B**: System MUST enforce a maximum of 10 conversation turns per session, after which users are prompted to summarize or start a new session
- **FR-010C**: System MUST store belief state and conversation context in Redis with automatic TTL expiration
- **FR-010D**: System MUST propagate trace_id across all service calls for end-to-end request tracking
- **FR-010E**: System MUST emit structured JSON logs for all operations

**Colloquial Expression and Terminology Mapping**:
- **FR-011**: System MUST support colloquial expression mapping to formal document terminology
- **FR-012**: System MUST expand queries with related terms and synonyms to improve recall
- **FR-013**: System MUST support the following colloquial term mappings (minimum):
  - **Time expressions**: 去年→2024年, 今年→2025年, 去年年底→2024年11月/12月, 上个月→previous month
  - **Topic mappings**: 防火→消防, 加班→值班/节假日安排, 涨工资→超额利润分享/薪酬福利, 开会→会议通知/会议纪要
  - **Document type mappings**: 规定/规矩→办法/细则/规定, 文件→[所有公文类型], 开会文件→会议通知/会议纪要
- **FR-014**: System MUST maintain a knowledge graph of document types, organizations, and content categories
- **FR-015**: System MUST support the following content categories (from document analysis):
  - **党建工作**: 党风廉政、党纪学习教育、党员大会、党总支工作、党支部建设、政治理论学习
  - **人事工作**: 干部任免、选举工作、评优表彰、政治审查
  - **安全生产**: 安全生产管理、消防管理、应急预案、防汛工作、安全检查、安全生产月
  - **行政管理**: 节假日安排、值班工作、档案管理、部门调整、固定资产盘点
  - **制度建设**: 办法、细则、规定、规则、方案、规划
  - **工会工作**: 工会选举、职工代表大会、工会采购、福利慰问

**Query Enhancement and Routing**:
- **FR-016**: System MUST provide proactive suggestions based on available document inventory
- **FR-017**: System MUST handle time-relative expressions and convert them to specific dates
- **FR-018**: System MUST provide query improvement suggestions when queries are too broad
- **FR-019**: System MUST detect topic changes and update conversation context accordingly
- **FR-020**: System MUST support clarification requests when queries are ambiguous or low confidence
- **FR-021**: System MUST route queries to appropriate processing logic based on topic class (meta_info vs business_query)

**Business Domain Classification**:
- **FR-022**: System MUST classify queries into business domains based on extracted keywords with priority ordering
- **FR-023**: System MUST support the following business domains with keyword mappings:
  - **finance** (财务报销): 报销, 差旅, 住宿, 餐饮, 交通, 费用, 预算, 资金, 发票
  - **hr** (人力资源): 绩效, 薪酬, 考勤, 培训, 人力, 组织, 招聘
  - **archive** (档案管理): 档案, 归档, 保密, 文档
  - **safety** (安全生产): 安全, 应急, 生产安全
  - **governance** (公司治理): 董事会, 经理层, 决策, 三重一大, 治理
  - **it** (信息化): 信息化, 软件, 系统, 网络
  - **procurement** (采购): 采购, 合同, 供应商
  - **admin** (行政后勤): 行政, 车辆, 办公用品, 后勤, 会议, 公文, 印章
  - **party** (党建): 党建, 党务, 党委
  - **other**: (以上都不含时)
- **FR-024**: System MUST support sub-domain classification for finance domain:
  - **accommodation** (住宿): 住宿, 酒店, 宾馆
  - **meal** (餐饮): 餐饮, 餐费, 伙食, 工作餐
  - **transport** (交通): 交通, 机票, 高铁, 火车, 出租车, 打车
  - **other** (其他): 其他费用, 杂费
- **FR-025**: System MUST use business domain classification to route queries to specialized processing logic
- **FR-026**: System MUST use business domain classification to select appropriate prompt templates
- **FR-027**: System MUST handle queries with keywords matching multiple domains using priority ordering

**Meta-info Query Handling**:
- **FR-028**: System MUST recognize meta-info query patterns:
  - has_count_query=true + keywords含"制度"
  - keywords含"制度" + 含"哪些/目录/清单/列表"
  - keywords含"检索/搜索/查找/查询" + "制度"
  - temporal非空 + keywords含"制度/发布/生效"
  - keywords含"版本/修订/更新/历史版本"
  - keywords含"归口/负责部门/解释权"
  - keywords含"模板/表单/下载/范本"

**Business Query Handling**:
- **FR-029**: System MUST recognize business query patterns:
  - quantifiers含"多少" + keywords含"标准/额度/上限/限额"
  - keywords含"怎么办/如何/流程/步骤/操作" 且不含"制度"
  - keywords含"凭证/限制/条件/要求/规则"
  - keywords含"可以报/能报/适用/范围"

**Structured Query Generation**:
- **FR-030**: System MUST generate three independent search question variations (q1, q2, q3) for each user query
- **FR-031**: System MUST extract must_include terms (3-6 items) representing core anchor terms for the query
- **FR-032**: System MUST generate expanded keywords (5-10 items) including synonyms and colloquial variations
- **FR-033**: System MUST use collected slots from belief_state to fill query templates: topic, expense_type, city, level, province_relation
- **FR-034**: System MUST support domain-specific question generation:
  - **Business query domain**: Incorporate city/expense_type/level into questions with topic-specific templates (standard/rule/process/scope)
  - **Meta info domain**: Generate questions for subtypes (directory/count/search/version/effective_date/responsibility/templates/definitions)
  - **Unknown domain**: Perform neutral rewriting without forcing unrelated domain terms
- **FR-035**: System MUST add location context based on city (explicit city name) or province_relation (省内/省外/跨省/全国)
- **FR-036**: System MUST expand expense_type with colloquial terms: 住宿/酒店, 餐饮/餐补/伙食补助, 交通/打车/高铁
- **FR-037**: System MUST prevent forcing domain-specific terms into unrelated queries (e.g., no "报销" in safety queries)
- **FR-038**: System MUST output query generation results in structured JSON format with fields: q1, q2, q3, must_include, keywords

### Key Entities

**Structured Extraction Entities**:
- **Extracted Elements**: Represents the structured output from query parsing, containing:
  - **Temporal**: year (四位数年份), date (完整日期), time_range (近三年/去年/上半年), relative_time (今年/本月)
  - **Spatial**: organization (粤东科/党总支/工会/各党支部), location_type (公司级/部门级/多部门)
  - **Document**: doc_type (通知/通报/报告/请示/纪要等), doc_number (文号如〔2024〕33号)
  - **Knowledge Base**: company_id (公司标识，如 N000002), file_type (文件类别: PublicDocDispatch/发文, PublicDocReceive/收文)
  - **Content**: topic_keywords (主题关键词列表), policy_names (完整制度名称)
  - **Quantity**: has_count_query (布尔值), numbers (明确数字列表), quantifiers (量词列表)

- **Knowledge Base Route**: Represents the target knowledge base(s) for document retrieval:
  - **company_id**: Company identifier provided by external system (e.g., N000002)
  - **file_type**: PublicDocDispatch (发文/outgoing) | PublicDocReceive (收文/incoming) | both (when unclear)
  - **search_mode**: single (search one specific knowledge base) | dual (search both when file type cannot be determined)
  - **collection_names**: Knowledge base collections to search (single or both based on determination)

- **Query Classification**: Represents the classification result for routing:
  - **topic_class**: meta_info (询问文档信息) | business_query (询问文档内容) | unknown
  - **is_follow_up**: true | false (基于是否包含指代词)
  - **confidence**: high | medium | low (基于提取明确性)

**Conversation Management Entities**:
- **Conversation Session**: Represents a multi-turn dialogue session with a user, containing the conversation history, extracted context, and current state

- **Conversation Turn**: Represents a single exchange in the conversation, including the user input, system response, extracted elements, and classification

- **Belief State**: Represents the accumulated context and understanding from the conversation, including:
  - history (previous turns with extracted elements)
  - established_dimensions (confirmed values for temporal, spatial, document, content)
  - pending_clarifications (dimensions that need user input)

**Knowledge Entities**:
- **Colloquial Term Mapping**: Represents a mapping from informal expressions to formal document terminology, including the colloquial term, formal equivalents, context applicability, and confidence score

- **Content Category**: Represents a category of document content (e.g., 党建工作, 人事工作) with related terms, subcategories, and keyword expansions

- **Query Context**: Represents the accumulated context from a conversation, including established dimensions like year, organization, topic, and document type

- **Suggestion Template**: Represents a proactive suggestion template for common query patterns, including trigger conditions, suggestion text, and available options

**Routing Entities**:
- **Query Route**: Represents the determined processing path based on topic_class:
  - meta_info → Document inventory search and listing
  - business_query → Document content retrieval and QA
  - unknown → Clarification and information gathering

- **Business Domain Classification**: Represents the business area classification for specialized routing:
  - **business_domain**: finance | hr | archive | safety | governance | it | procurement | admin | party | other
  - **sub_domain**: For finance domain - accommodation | meal | transport | other (empty string for other domains)
  - **confidence**: Based on keyword match strength and domain specificity

- **Generated Retrieval Queries**: Represents the final structured output for document retrieval:
  - **q1, q2, q3**: Three independent question variations for the search
  - **must_include**: Core anchor terms that must appear in results (3-6 items)
  - **keywords**: Expanded keywords with synonyms and colloquial terms (5-10 items)
  - **domain_context**: Query type and domain-specific template used for generation

## Non-Functional Requirements

### Performance
- Average response time per conversation turn is under 2 seconds (measured at p95)

### Reliability
- System availability target: 99.5% (approximately 3.6 hours of downtime per month)
- Single-instance deployment with simple failure recovery mechanism

### Observability
- Structured JSON logging for all operations
- Trace ID propagation across all service calls (consistent with existing architecture using Langfuse)
- Conversation context and belief state stored in Redis with TTL-based expiration

### Scalability
- Session state managed via Redis to support potential future horizontal scaling
- Maximum 10 conversation turns per session to prevent resource exhaustion

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 70% of users successfully find their target document within 3 conversation turns (measured by task completion rate)
- **SC-002**: Colloquial expression recognition accuracy reaches 85% (measured by correct mapping rate)
- **SC-003**: Average conversation length decreases by 40% over 60 days as users learn more effective query patterns (measured by average turns per successful search)
- **SC-004**: 90% of users report satisfaction with the conversational interface (measured through user feedback surveys)
- **SC-005**: Query recall improves by 50% through synonym and related term expansion (measured by relevant documents found)
- **SC-006**: Average response time per conversation turn is under 2 seconds (measured at p95)
- **SC-007**: 80% of users successfully use natural language queries without needing to learn search syntax (measured by first-time success rate)
- **SC-008**: Conversation context is correctly maintained across 95% of follow-up questions (measured by context accuracy)

## Assumptions

- Users prefer natural language interaction over keyword-based search
- The existing document corpus (82 documents in 2024 folder) is representative of the full document collection
- Colloquial terms are relatively stable within the user community and can be systematically mapped
- Users are willing to engage in multi-turn dialogue to improve search results
- The LLM can accurately parse Chinese natural language and extract query dimensions
- Conversation sessions are typically short (under 10 turns) and focused on finding specific documents
- Users may switch topics within a session, requiring context management
- Time-relative expressions should be interpreted relative to the current date or document context

## Dependencies

- Feature 005 (RAG QA Pipeline) for the query processing pipeline
- Feature 006 (Query Quality Enhancement) for dimension analysis
- LiteLLM gateway for LLM access (from feature 001)
- Prompt Service for conversation templates (from feature 003)
- Vector database for document content analysis (from feature 001)

## Out of Scope

- Voice input or speech recognition (assumes text-based input only)
- Multi-user collaborative conversations (single-user sessions only)
- Long-term conversation history across days (sessions expire after reasonable timeout)
- Sentiment analysis or emotional response to user frustration
- Automatic document content extraction or OCR (assumes documents are already indexed)
- Cross-language support (assumes Chinese-only interaction)
- Learning from user behavior to improve mappings (static mappings unless explicitly updated)
- Integration with external knowledge sources beyond the document corpus

## Document Content Analysis Reference

Based on analysis of 82 documents in `D:\project\OA\发文(2)\2024`, the following content categories have been identified:

## Structured Output Format

The system produces structured output for each user query to enable precise routing and context management:

### Extraction Output Schema

```json
{
  "extracted_elements": {
    "temporal": {
      "year": ["2024"],
      "date": [],
      "time_range": ["去年"],
      "relative_time": ["去年"]
    },
    "spatial": {
      "organization": ["粤东科", "党总支"],
      "location_type": "公司级"
    },
    "document": {
      "doc_type": ["通知"],
      "doc_number": ["〔2024〕33号"]
    },
    "knowledge_base": {
      "company_id": "N000002",
      "file_type": "PublicDocDispatch",
      "collection_name": "N000002_PublicDocDispatch"
    },
    "content": {
      "topic_keywords": ["安全生产", "管理", "办法"],
      "policy_names": []
    },
    "quantity": {
      "has_count_query": false,
      "numbers": [],
      "quantifiers": []
    }
  },
  "classification": {
    "topic_class": "meta_info | business_query | unknown",
    "is_follow_up": "true | false",
    "confidence": "high | medium | low",
    "business_domain": "finance | hr | archive | safety | governance | it | procurement | admin | party | other",
    "sub_domain": "accommodation | meal | transport | other | \"\""
  }
}
```

### Query Type Classification Rules

**meta_info** (highest priority):
1. has_count_query=true + keywords含"制度"
2. keywords含"制度" + 含"哪些/目录/清单/列表"
3. keywords含"检索/搜索/查找/查询" + "制度"
4. temporal非空 + keywords含"制度/发布/生效"
5. keywords含"版本/修订/更新/历史版本"
6. keywords含"归口/负责部门/解释权"
7. keywords含"模板/表单/下载/范本"

**business_query**:
1. quantifiers含"多少" + keywords含"标准/额度/上限/限额"
2. keywords含"怎么办/如何/流程/步骤/操作" 且不含"制度"
3. keywords含"凭证/限制/条件/要求/规则"
4. keywords含"可以报/能报/适用/范围"

**unknown**: None of the above patterns match

### Follow-up Detection Rules

- Contains pronouns: "这/那/这个/那个/它/上述/前面/上面"
- AND belief_state has previous turn
- THEN is_follow_up = "true" and inherit relevant context

### Business Domain Classification Rules

The system classifies queries into business domains using keyword-based matching with priority ordering:

**Domain Keyword Mappings** (by priority):

| Domain | Keywords | Description |
|--------|----------|-------------|
| finance | 报销, 差旅, 住宿, 餐饮, 交通, 费用, 预算, 资金, 发票 | 财务报销 |
| hr | 绩效, 薪酬, 考勤, 培训, 人力, 组织, 招聘 | 人力资源 |
| archive | 档案, 归档, 保密, 文档 | 档案管理 |
| safety | 安全, 应急, 生产安全 | 安全生产 |
| governance | 董事会, 经理层, 决策, 三重一大, 治理 | 公司治理 |
| it | 信息化, 软件, 系统, 网络 | 信息化 |
| procurement | 采购, 合同, 供应商 | 采购 |
| admin | 行政, 车辆, 办公用品, 后勤, 会议, 公文, 印章 | 行政后勤 |
| party | 党建, 党务, 党委 | 党建 |
| other | (none of the above) | 其他 |

**Sub-domain Classification** (only for finance domain):

| Sub-domain | Keywords | Description |
|------------|----------|-------------|
| accommodation | 住宿, 酒店, 宾馆 | 住宿费用 |
| meal | 餐饮, 餐费, 伙食, 工作餐 | 餐饮费用 |
| transport | 交通, 机票, 高铁, 火车, 出租车, 打车 | 交通费用 |
| other | 其他费用, 杂费 | 其他费用 |

**Priority Handling**:
- When keywords match multiple domains, select the highest priority domain (finance > hr > archive > safety > governance > it > procurement > admin > party > other)
- Sub-domain is only populated when business_domain = "finance"

### Example Extractions

| User Query | Extracted Elements | Classification | Business Domain |
|------------|-------------------|----------------|-----------------|
| "2024年发布了多少个制度" | year:[2024], has_count_query:true, keywords:[制度,发布] | meta_info | other |
| "关于安全生产的通知有哪些" | keywords:[安全生产,通知,哪些] | meta_info | safety |
| "经理级别的住宿标准是多少" | level:[经理], keywords:[住宿,标准], quantifiers:[多少] | business_query | finance / accommodation |
| "上海呢" (after 北京 context) | organization:[上海], is_follow_up:true, inherit keywords | business_query | (inherited) |
| "帮我找去年的消防安全规定" | relative_time:[去年], keywords:[消防,安全,规定] | business_query | safety |
| "关于差旅费报销的规定" | keywords:[差旅,报销,规定] | business_query | finance |
| "员工绩效考核办法" | keywords:[员工,绩效,考核,办法] | business_query | hr |
| "档案管理工作的规定" | keywords:[档案,管理,规定] | business_query | archive |
| "党建工作的相关文件" | keywords:[党建,文件] | business_query | party |

### Query Generation Output Schema

The final output for document retrieval:

```json
{
  "q1": "北京住宿费报销标准是多少",
  "q2": "北京住宿费用上限是多少",
  "q3": "北京经理级住宿标准如何规定",
  "must_include": "报销, 住宿, 标准, 北京",
  "keywords": "报销, 住宿/酒店, 标准, 上限/额度, 北京, 凭证/单据"
}
```

### Query Generation Rules by Domain

**Business Query Domain** (expense rules, policies):
- Incorporate collected slots: city, expense_type, level
- Use topic-specific templates:
  - standard: "…报销标准是多少？" / "…上限/额度是多少？"
  - rule: "…需要哪些单据/条件/限制？"
  - process: "…流程/步骤是什么？"
  - scope: "…是否可以报销/报销范围是什么？"
- Add location context: city name or province_relation (省内/省外/跨省/全国)
- Expand expense_type with colloquial terms: 住宿/酒店, 餐饮/餐补, 交通/打车/高铁

**Meta Info Domain** (document inventory):
- directory: "公司现行制度目录有哪些？"
- count: "公司共有多少份制度？"
- search: "如何检索安全生产相关制度？"
- version: "制度版本与修订规则是什么？"
- effective_date: "制度何时生效与失效？"
- responsibility: "制度解释权归属如何规定？"
- templates: "制度配套的表单/模板在哪里下载？"
- definitions: "制度中的名词术语如何定义？"

**Unknown Domain**:
- Neutral rewriting of user input
- No forced domain-specific terms
- Light structuring for readability

### Primary Content Categories

1. **党建工作 (Party Building)** - 25 documents
   - 党风廉政建设
   - 党纪学习教育
   - 党员大会/换届选举
   - 党总支/党支部建设
   - 政治理论学习
   - 二十届三中全会精神学习

2. **人事工作 (Personnel)** - 15 documents
   - 干部任免
   - 党支部选举
   - 评优表彰
   - 政治审查

3. **安全生产 (Safety Production)** - 12 documents
   - 安全生产管理
   - 消防管理（生命通道、消防宣传月）
   - 应急预案（龙舟水防护、防汛）
   - 安全生产月活动
   - 安全生产治本攻坚

4. **行政管理 (Administration)** - 18 documents
   - 节假日安排及值班
   - 档案管理
   - 部门职责调整
   - LOGO征集
   - 固定资产盘点
   - 综合检查

5. **制度建设 (Institutional Building)** - 8 documents
   - 管理办法（信息化、市场、应收款项、工会采购）
   - 实施细则（党风廉政、超额利润分享）
   - 工作规则（董事会秘书）
   - 方案（安全生产月、消防宣传月、党纪学习）

6. **工会工作 (Labor Union)** - 4 documents
   - 工会选举
   - 职工代表大会
   - 提案征集

### Colloquial Term Mapping Examples

| Colloquial Term | Formal Terminology | Context |
|----------------|-------------------|---------|
| 防火 | 消防 | Safety documents |
| 加班 | 值班/节假日安排 | Personnel/admin |
| 涨工资 | 超额利润分享/薪酬福利 | Compensation |
| 开会 | 会议通知/会议纪要 | Meetings |
| 评优 | 优秀部门/优秀员工评选 | Evaluation |
| 换届 | 选举/补选 | Organization |
| 纪律 | 党纪/党风廉政 | Party discipline |
| 去年 | 2024年 | Time reference |
| 今年 | 2025年 | Time reference |
| 年底 | 11月/12月 | Time reference |
| 规定 | 办法/细则/规定 | Document type |
| 规矩 | 办法/细则/规定 | Document type |
| 文件 | [所有公文类型] | Generic reference |
