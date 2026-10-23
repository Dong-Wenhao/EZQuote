# EzQuote API 1.6.1

Base URL: http://127.0.0.1:8765/api

普通工作台 API 除 health、setup 和 login 外，需要 Authorization: Bearer TOKEN。会话为 12 小时。老板和员工账号在首次 setup 时创建，密码散列保存，API 不接受客户端指定角色。手机 API 使用专用签名令牌，决定操作另需老板密码，详见下文。

| 方法与路径 | 权限 | 作用 |
| --- | --- | --- |
| GET /health | 公开 | 连通性、版本和是否已设置 |
| POST /setup | 尚无账号时 | shop_name、boss_password、staff_password |
| POST /login | 公开 | username 为 boss 或 staff；password |
| POST /logout | 已登录 | 撤销当前会话 |
| GET /me | 已登录 | 当前账号和角色 |
| GET /shop | 已登录 | 店铺资料 |
| PUT /shop | 老板 | name、address、phone、terms |
| GET /integrations/status | 已登录 | 仅返回 AI 与手机通知启用、配置状态 |
| GET /integrations | 老板 | 返回非秘密设置、凭据是否已存的布尔值 |
| PUT /integrations | 老板 | 保存 ConnectionUpdate；空凭据保留，clear_ai_key / clear_wa_token 显式清除 |
| GET /catalog | 已登录 | 当前目录版本和商品 |
| GET /catalog/template | 已登录 | 下载合成 Excel 样例 |
| POST /catalog/preview | 老板 | 检查上传并返回表头、映射、工作表、商品和错误行 |
| POST /catalog/import | 老板 | 重新验证并写入新目录版本 |
| POST /inquiries/parse | 已登录 | text；返回语言、行明细、候选和补充问题 |
| POST /quotes | 已登录 | 创建报价草稿，request_key 保证重复请求不重复建单 |
| GET /quotes | 已登录 | 老板看全店；员工看自己创建的报价 |
| GET /quotes/ID | 有权访问报价 | 报价、当前批准、批准版本和活动日志 |
| PUT /quotes/ID | 有权访问报价 | expected_revision 和新草稿内容，生成新版本 |
| POST /quotes/ID/submit | 有权访问报价 | expected_revision；提交到老板收件箱 |
| POST /quotes/ID/approve | 老板 | expected_revision；固定快照并生成文件 |
| POST /quotes/ID/reject | 老板 | expected_revision、reason |
| POST /quotes/ID/export | 有权访问报价 | expected_revision；从已有批准快照重试 |
| GET /quotes/ID/pdf?revision=N | 有权访问报价 | 只能读取已批准版本 |
| POST /quotes/ID/activity | 有权访问报价 | revision、action 为 REPLY_COPIED、PDF_PREPARED 或 REPLY_INSERTED |
| GET /exports/ledger | 已登录 | 从批准快照和日志生成全店导出表 |
| GET /notifications | 已登录 | 当前角色的待审通知 |
| POST /quotes/ID/mobile-link | 有权访问报价 | expected_revision；准备单笔、限时的手机审批 URL |
| POST /quotes/ID/phone-notification | 有权访问报价 | expected_revision；手动通知或重试；ACCEPTED / UNKNOWN 状态需 confirm_resend=true |
| POST /mobile/review | 手机审批令牌 | 查看令牌所对应的单个当前版本 |
| POST /mobile/decision | 手机令牌与老板密码 | expected_revision、decision 为 approve / return、boss_password、reason |
| POST /mobile/pdf | 手机审批令牌 | 下载这一版已经批准且导出完成的 PDF |

Excel 上传体：

    {
      "filename": "products.xlsx",
      "content_b64": "BASE64_OF_XLSX",
      "mapping": {"unit_price": "My Price"},
      "sheet_name": "Products"
    }

mapping 和 sheet_name 可以省略。最多 5 MB，不解析宏；单元格公式不作为价格计算来源。服务不主动回写用户原 Excel。

草稿体：

    {
      "customer": "Demo 01",
      "inquiry": "A牌50kg水泥20袋",
      "language": "zh",
      "items": [{"sku":"CEM-A-50","quantity":"20"}],
      "notes": "",
      "source_confirmed": true,
      "request_key": "UNIQUE-CLIENT-UUID"
    }

修改时再附加 expected_revision。服务器从当前目录读取价格；额外传 unit_price、role 或 approved_by 会被拒绝。金额返回两位小数字符串，数据库时间为 UTC；界面按电脑的本地时间显示。

1.1 草稿可附加 source，也可省略或为 null：

    {
      "kind": "whatsapp",
      "tab_id": 5,
      "page_session": "CONTENT-SCRIPT-SESSION-UUID",
      "chat_token": "CHAT-VIEW-UUID",
      "chat_title": "Synthetic Customer",
      "message_id": "WHATSAPP-DOM-MESSAGE-ID",
      "anchor": "CAPTURE-ANCHOR-UUID"
    }

source 是用户核对后的聊天关联元数据，不能授权发送消息或批准报价。按 quote_id、revision 保存，不覆盖旧版本；报价详情返回当前 source。手工录入及 1.0 的报价返回 null。修订时传 null 会清除新版本的关联，旧版本关联保留。

REPLY_INSERTED 仅表示内容已填进聊天输入框，不表示 WhatsApp 已发送或送达。插件回填批准回复前会重新读取服务器的版本、批准状态和回复正文，不使用页面传来的金额或自由文本。回填完成后记录此事件；不能把它用于发送统计。

状态流：DRAFT → PENDING_APPROVAL → EXPORT_PENDING → COMPLETED。老板退回后为 REJECTED；编辑任何状态都会生成新版本并回到 DRAFT。批准快照不会被修订覆盖。

HTTP 401 需要登录，403 无权限，409 状态或版本冲突，422 输入验证失败。已批准但导出失败会返回业务状态 EXPORT_PENDING，不能仅依据 HTTP 200 显示“全部完成”。

主服务继续只绑定 127.0.0.1:8765，接受本地工作台与 Chrome 扩展来源。手机网关绑定 127.0.0.1:8766，只暴露 /mobile、其脚本样式、/health，以及 /api/mobile/review、decision、pdf。公网隧道应连接 8766；网关没有账号、目录、配置或完整工作台接口。

手机 API 的 Authorization: Bearer TOKEN 使用签名审批令牌，不接受普通登录会话代替。令牌放在通知 URL 的片段中，页面再用请求头提交，避免进入服务访问日志。批准和退回还要验证现有老板密码，错误次数有限制；链接与业务版本在同一事务中检查和消费。

连接设置字段与部署步骤见“接入AI与手机通知_1.2.md”。AI 解析响应增加 ai_state（disabled / used / fallback），成功时 method 为 openai_catalog；回退时 method 为 catalog_rules 并附 warning_code。调用者不能把回退显示为模型成功。

报价详情增加 mobile_notification，包含 status、error、attempts 和 updated_at。状态为 PENDING、WAITING_GATEWAY、SENDING、ACCEPTED、FAILED、UNKNOWN、PAUSED 或 CANCELLED。ACCEPTED 仅表示 WhatsApp API 受理；无送达证明。通知网络异常或中断不会自动重发。

WhatsApp 通知当前只发送给明确配置的老板号码，不自动发送客户回复。单店铺与固定 boss / staff 账号范围保持。


## 1.3 经营数据和需求工作流

| 方法与路径 | 权限 | 作用 |
| --- | --- | --- |
| GET /business | 已登录 | 经营版本、库存、配送、规则及历史概览，不返回原始历史行 |
| GET /business/template | 已登录 | 下载 business_demo.xlsx |
| POST /business/preview | 老板 | Upload 格式，校验 Products、Inventory、History、Delivery、Rules |
| POST /business/import | 老板 | 同格式，原子导入目录及经营版本；同份文件重复导入幂等 |
| POST /requirements/review | 已登录且有报价权限 | 核对原始询价与最终商品、配送，返回问题或 review_id |
| POST /pricing/preview | 已登录 | items、inquiry、area、fulfilment、review_id；可选 quote_id，复核时排除本单历史 |
| POST /quotes/ID/outcome | 有权访问报价 | 仅批准后记录 open/won/lost；附 expected_revision、expected_outcome_version、note、可选 actual_delivery_cost |

/api/inquiries/parse 新增 mode=requirements、area、fulfilment（auto/delivery/pickup），返回 requirement JSON、best_match、alternatives、库存和三语理由。省略 mode 继续使用旧目录解析接口。

创建与修订报价可增加 pricing_enabled=true、delivery_area 和 fulfilment（delivery/pickup）。导入经营数据后，该模式为必需，客户端不能设为 false 绕开库存或定价策略。旧版已批准快照继续可读取；待审旧版需修改后重审。

/api/quotes/ID/approve 除 expected_revision 外，接受 discount_pct、freight、pricing_note。省略两个数值代表老板采用保存的建议。额外 total、unit_price 等字段仍拒绝。后台执行最高折扣及最低预估毛利核对，decision 和批准快照在同一事务写入。

报价 pricing 对象含 requirement、recommendation、decision。recommendation 保存原价、建议折扣与运费、建议总额、参考样本数量、转化率、经营版本、库存快照、成本估计、三语理由。decision 在批准前为 null；批准后保存 accepted/edited、折扣金额、运费、最终合计、批准人、时间、说明。

报价 total 在待审时是建议总额，不能当作已批准价格。正式客户回复只来自批准快照。客户 outcome 与报价 status 分开，批准不自动成交。

客户结果用 expected_outcome_version 防止覆盖别人新记录；同样结果重复保存不新增版本。同一 Quote ID 只采用最新已评价的版本统计，当前单修订时排除自身旧历史。未知实际配送成本不进入运费成本均值。

手机 decision 也可带 discount_pct、freight、pricing_note，仍需老板密码及签名链接。review 中增加 pricing，公开网关路径范围保持单笔审批。

## 1.4 分步工作台

1.4 引入分步页面。本版后台与扩展均为 1.6.1；完整经营报价增加以下强制核对契约，旧客户端需同步更新。

GET /api/quotes 的每项新增 outcome（open/won/lost），来自当前报价版本的客户结果，未记录时为 open。员工仅可列出自己的报价，老板可查看本店列表。返回最新 200 笔。前端用 PENDING_APPROVAL 统计待审批，用 COMPLETED/EXPORT_PENDING 且 outcome=open 统计待跟进，用 won/lost 筛选已结束。

页面保存草稿中的 step 和 needsReparse 仅供同一会话恢复界面，不能代替后端正式报价或审批记录。改动原询价后需要重新整理商品。


## 1.5 需求核对契约

`POST /requirements/review` 请求：

```json
{
  "inquiry": "Need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam.",
  "items": [{"sku":"CEM-A-FAST-50","quantity":"20","source_id":null}],
  "area":"Shah Alam",
  "fulfilment":"delivery",
  "corrections":[],
  "quote_id":null,
  "expected_revision":0
}
```

服务端重新解析原文，不采用客户端的 fulfilment 覆盖原文事实。source_id 来自解析结果；商品行数相同时可省略 source_id 并按行顺序映射，数量仍会独立核对。增删行时应保留各自的 source_id，未知或重复来源拒绝。

返回 `can_quote=false` 时，没有可用于正式定价的 review_id。`issue_details` 含 id、code、field、source_id、source_text、原始 span、severity、target，以及 expected_value 或 choices。数量 token 另保留 raw、value、unit、原文 offset；未识别的尾部不会代替完整数字。

人工修正应传 `corrections:[{"issue_id":"返回的id","value":"具体确认值","reason":"向客户核实的原因"}]`。quantity 对应规范化数字字符串；sku 对应具体 SKU；area 和 fulfilment 对应实际最终值；条件歧义用返回的 choices；取消原文商品用 `{"action":"remove","source_id":"原来源"}`；新增商品用 `{"sku":"具体SKU","quantity":"数量"}`。原因至少 3 个字符。不接受 resolved=true、未知问题 ID、过期问题、错误值或多余字段。

规格确已选为原文允许的具体 SKU，可由服务端自动核实。未知商品、修改数量、改变用途/偏好/品牌等仍需处理对应问题；库存不足始终执行合计校验。无法拆分的多商品或条件归属不明要求修改原文，不能用通用确认绕过。

核对通过后返回随机 review_id，持久化原始事实、最终选择、问题处理、操作者、时间、解析器版本、目录与经营版本。摘要绑定原文、最终 SKU/数量、配送、修正、来源及报价上下文。review_id 只属于该用户和输入，不能给另一报价/版本使用；核对后改输入或经营数据返回 409 review_stale。

完整经营模式的 `/pricing/preview`、`POST /quotes`、`PUT /quotes/ID` 必须带 review_id。修订核对时传 quote_id 和当前 expected_revision；PUT 再传同一个 expected_revision。preview 可带 quote_id，用于排除本单历史。直接创建、修订、提交和首次老板批准均有服务端校验，手机批准复用同一检查。重复创建仍按 request_key 与核对内容摘要保证幂等。

报价详情新增 `review` 与 `review_required`。旧的未批准经营报价缺少当前核对时，必须创建经过核对的新版本；已批准快照与 PDF 保留。后台迁移只新增 requirement_reviews、quote_reviews。人工处理写入 REQUIREMENTS_REVIEWED 日志，批准快照包含 requirement_review；pricing.requirement 包含核对后的需求、选择及记录关联。

结构化错误 detail 中的 code 可为 review_stale、review_required、invalid_correction、invalid_source_segment、duplicate_source_segment 等。409 表示需重新核对当前输入，422 表示请求值不合法；can_quote=false 的 200 只表示已检查并列出待处理问题，不代表可报价。


## 1.5.1 复核补充

1.5.1 使用 requirements_rules_v3。数值先扫描完整 token，范围和二选一数量返回 multiple_quantities；此类问题要求核实后编辑原文，不能靠更正值确认绕过。非法选定数量在规范化前校验，返回 422。新增项问题返回正确的 item_index，匹配具体 SKU 和数量。传统价目表解析也共用完整数字扫描器，但该模式仍为人工核对价格表，不提供经营库存与配送策略。

手机 review 的 quote 新增 review_required。手机页显示 pricing.requirement.resolutions 中的人工更正，过期核对禁止批准但允许退回。URL 片段变化会重新加载限定报价；旧请求不会覆盖另一笔报价，密码与编辑值随链接清空。

浏览器本地草稿记录 parserVersion；版本不符时保留原文，要求重新整理并清除旧更正缓存。服务端仍独立检查 review_id 和解析版本，本地缓存不构成授权。

## 1.5.2 数字完整性与未知片段

1.5.2 使用 requirements_rules_v4。扫描以单位为锚点，先获取整个数字表达，再验证格式；数字之间的未知字符与异常连续分隔不能被跳过后重试尾数。NFKC 仅用于判定完整表达是否为范围，不直接转换数量或整份原文；raw 与 span 始终来自原文，因此没有全局字符规范化造成的位置偏移。20／30 返回 multiple_quantities；1_020、未知符号与异常连续分隔返回 quantity_format，不提供默认数量。

商品连接词两侧有一侧已识别时，另一侧只有明确归类的偏好、规格、物流或礼貌表达可以附回。其他片段保留为需求项，目录没有商品也不能丢弃。缺商品/数量返回 unknown_product/quantity；直接删除该项仍产生 missing_product，须按原有契约记录具体取消和原因。带未知内容的偏好续行与物流尾部也保留。

没有解决问题时 review 不生成 review_id；直接定价返回 422 review_required，缺核对的创建返回 409 review_stale。升级前 v3 核对记录及缓存不能用于新报价，旧未批准单须保存经过新核对的版本。已批准快照及 PDF 不改写。支持范围仍为常见建材表达，不是任意自然语言的完整语义识别。


## 1.5.3 原文覆盖与页面请求归属

当前解析器为 requirements_rules_v5。backend/number_words.py 只计算符合支持语法的完整中英马来数字；不再任意相加多个词，也不会把不支持的数量级忽略后取尾数。AI 证据数值校验与本地扫描共用该函数。异常文字数量保留 raw 并返回 quantity_format。

在已匹配商品的原文中，数量、规格、商品别名、明确条件、配送和常见请求用语之外仍有内容时，返回新的 blocking 问题 uncovered_text，附 uncovered_text 字段作为未解释片段，span 和 source_text 保留原文。该问题不能用通用更正值或理由消除，须补充、分行或修改原文后重新整理；review 不发出 review_id。明确的未知独立商品仍沿用 unknown_product、quantity 及显式取消契约。规则会保守追问部分正常但不在支持范围的表达，不保证理解任意自然语言。

英语否定支持常见直引号及弯引号的 don't/doesn't；无法归类的否定后缀也会被覆盖检查拦下。CR、Unicode 行分隔符等保留原始偏移后分行。

电脑页面以工作区序号和报价 ID/修订约束异步响应。打开、轮询、保存、提交、审批、退回、结果登记及文件操作只更新发起时对应的上下文。保存期间换到新草稿时，已经授权的原单保存提交仍正常完成，新草稿不清空。保存前异步核对完成后再次检查来源确认。PDF 下载和准备记录固定到原报价及版本；旧会话的失败响应不能清除新会话登录。

升级后旧未批准的 v4 核对须重新生成，旧草稿须重新整理；已批准快照不追溯重算。


## 1.5.4 长询价的受控拒绝

完整经营模式的 parse 与 requirements/review 共用 understand → split_segments。拆分使用显式栈，先右后左入栈，保持原文左右顺序和 span；缓存原文商品提及位置，避免重复扫描大段尾部。保留原连接词判据及完整数量表达保护。

预算如下：商品需求最多 40 条（包括需要补充的未知商品）；原始非空片段最多 160；待处理区间最多 160；弹栈工作次数最多 320；累计扫描区间长度最多 512,000 字符。配送、问候、独立修饰先按原规则分类，不直接占商品额度，但仍占处理预算。任一预算超限均整体失败，不截取前 40 条，不写入核对编号或报价。有效报价请求体的 items 上限仍为 40。

预算异常由 CatalogError 统一返回 HTTP 422，响应为：

    {"detail":"Inquiry is too large. Use at most 40 products and submit smaller batches."}

中文、英文、马来语工作台将该稳定消息映射为对应的分批提示。text/inquiry 的 12,000 字符请求体上限继续由 Pydantic 验证，超长仍为 422 验证错误；两种错误都不是可报价结果。

这次不新增数据库表，不改变 requirements_rules_v5 或核对摘要格式，不重新计算既有已批准报价。性能目标和实际固定测试机结果见 VERIFICATION.md；2 秒目标不代表任意电脑、目录和输入的性能承诺。


## 1.6.1 界面资源

新增固定静态资源 theme.css，用于绿色主题与宽窄屏排版；本地工作台根路径的资源白名单仅增加该文件，/assets 仍提供扩展静态资源。Manifest、后台健康接口与手机网关版本统一为 1.6.1。新建、核对、定价、审批、PDF、Excel 和日志的业务合同保持原有规则，没有新增业务 API、角色或数据库表。
