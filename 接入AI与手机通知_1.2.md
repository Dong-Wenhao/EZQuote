# AI 与老板手机通知：本机接入说明

先把 1.2 代码替换到原项目，保留 data，然后用原 boss 账号进入完整工作台的“连接设置”。

本说明把账号配置和最终联调放在一起。代码已经准备好，真实服务能否使用还取决于你的 API 权限、额度、Meta 测试号码和网络。

## 一、AI 服务

1. 到 [OpenAI API 平台](https://platform.openai.com/api-keys) 创建你自己的 API key，并确认这个项目能够调用模型。
2. 在本机“连接设置 → AI 询价理解”填入 key。模型默认 gpt-5.4-mini，也可以填写你账号支持、可使用 Responses API 结构化输出的模型名称。
3. 勾选“启用真实 AI 接口”，保存连接设置。
4. 保存后 key 输入框清空，只显示已保存状态。以后留空会保留；勾选清除并关闭 AI 后，可以删除已存 key。

AI 会收到这次选中的询价原文，以及最多 300 个相关商品的名称、品牌、规格、单位和编码。程序不会额外附带聊天联系人信息或价目表价格字段。选中的原文本身若含个人信息，也会随原文提交。

模型负责拆分商品和理解数量。后台检查原文证据、品牌、规格、数量及目录匹配，金额由服务端按价目表计算。保存报价和批准仍由人确认。

界面会显示：

| 显示 | 含义 |
| --- | --- |
| AI 理解 + 价目表核对 | 本次得到模型结构化结果，并经过应用校验 |
| 本次使用商品目录规则 | 当前没有启用 AI |
| AI 暂不可用，本次改用目录规则 | 超时、凭据、模型权限、拒绝或输出校验出现问题；后面附错误码 |

接口调用会产生你账号的 API 使用量。程序不自动反复重试模型请求，模型失败时保留可见的规则回退。

## 二、让老板手机打开审批页面

电脑中的 127.0.0.1 地址只指向当前电脑。老板手机要打开通知中的 HTTPS 链接。

### 安装一次 cloudflared

在 Windows 新命令窗口运行：

    winget install --id Cloudflare.cloudflared --exact

安装完成后关闭旧命令窗口，再打开一个新窗口，检查：

    cloudflared --version

如果没有 winget，使用 [Cloudflare 官方下载页面](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/) 的 Windows 下载。也可以把适合你电脑的官方可执行文件重命名为 cloudflared.exe，放进本项目 tools 文件夹。

### 启动手机模式

1. 先按 Ctrl+C 停掉普通报价服务。
2. 在原项目双击 Start Mobile Windows.bat；或者在原文件夹的 cmd 中运行：

       python run.py --mobile

3. 程序会启动本机报价服务、独立手机入口和临时隧道。看到临时 HTTPS 地址后，保持命令窗口运行。
4. 用 boss 登录，进入“连接设置”，点“重新读取设置”。“手机审批 HTTPS 地址”通常已经自动填好。
5. 保存连接设置。

本机工作台继续使用 8765 端口；手机入口使用独立的 8766 端口。启动器只把 8766 交给隧道，手机入口只提供单笔查看、决定和 PDF，不提供账号、价格表或完整工作台接口。

临时入口用于开发演示，没有可用性保证，重启后域名会变化。旧通知里的地址可能失效；重启后应重新读取入口，再对仍待审的报价明确重发通知。长期部署需要固定 HTTPS 入口，把它指向独立手机入口服务。

### 可以先准备审批链接

即使暂时没有 Meta 凭据，只要手机入口已启动并保存，员工提交报价后也能点“复制手机审批链接”，手动转给老板，用来核对手机审批页面。它不会自动发送消息。

老板打开后，核对明细，输入首次创建店铺时设置的老板密码，再批准或退回。链接默认 60 分钟有效；报价修改后旧链接失效，重复点击不能重复批准。手机批准会使用同一套后台审批和归档逻辑。

## 三、接入 WhatsApp 手机通知

本插件使用 WhatsApp Cloud API 发通知，不复用 Chrome 中的 WhatsApp 登录会话。可以先使用 Meta 分配的测试业务号码作为通知发送方，员工使用插件的 WhatsApp 账号可以保持原样。

进入 [Meta WhatsApp 开发入门](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started)，在你自己的开发者账号中准备启用了 WhatsApp 业务消息的应用。按该账号的 API Setup / 快速入门页面取得测试发送方及访问令牌，并添加、验证实际老板作为测试接收方。界面名称以账号当前页面为准。

回到本机“连接设置”填写：

| 本机字段 | 填什么 |
| --- | --- |
| WhatsApp Phone Number ID | 业务发送号码对应的 ID，复制 Meta API 页面给出的值 |
| WhatsApp access token | 对应应用和业务号码的有效访问令牌 |
| 老板 WhatsApp 号码 | 实际接收通知的号码，含国家码；马来西亚号码以 60 开头，填写数字 |
| 号码确认 | 核对确实是老板的接收号码后勾选 |
| Graph API 版本 | 默认 v26.0；也可填账号示例中受支持的版本 |
| 手机审批 HTTPS 地址 | 由手机模式自动填入，或你配置好的固定入口 |

访问令牌可能有有效期和权限限制；过期后需要换新。测试接收方必须按 Meta 的测试号码要求添加。不要把服务凭据发进客户聊天或团队群。

### 开发测试：普通文字

为了先跑通，可在“通知方式”选择“开发测试：普通文字”。

由老板的实际接收号码先向 Meta 测试业务发送号码发一条消息，建立可用的服务窗口。普通文字需要在这个 24 小时服务窗口内发送；超出窗口会被接口拒绝，应改用已审核模板。

选择普通文字通知语言，勾选“提交报价时自动通知老板手机”，确认接收号码，保存。后续员工提交一笔报价时，后台会自动排队通知。

### 模板通知

模板模式需要 Meta 已审核通过的模板，正文包含四个位置参数，顺序固定为：

1. 报价编号；
2. 客户；
3. 金额；
4. 手机审批链接。

可以用下面的自编正文作为创建模板时的起点，审批结果由 Meta 决定：

    New quotation {{1}} requires approval.
    Customer: {{2}}
    Amount: {{3}}
    Review: {{4}}

模板名称可以申请为 quote_approval，语言代码需与已批准版本一致，例如 en_US。程序只填四个正文参数，当前不发送模板按钮或媒体头部参数。请选用与这一结构一致的模板。

Meta 自带的 hello_world 模板不符合这四个正文变量的约定，不要把它当成本插件的四参数报价模板。

## 四、只做一次完整联调

保持手机模式运行，老板和员工分别使用原账号。

1. 使用随包模拟价目表，员工在询价框输入：

       A牌50kg水泥二十袋，还有 Brand A PVC pipe 20mm five pieces

2. 先核对“AI 理解 + 价目表核对”标记是否出现。模型实际应拆出 20 袋 50kg A 牌水泥、5 根 20mm A 牌 PVC 水管。模拟价目表合计应为 RM413.75。
3. 员工核对来源和明细，点“确认明细并提交老板”。
4. 待审报价下方显示手机通知状态。老板在手机查看实际 WhatsApp 消息，点审批链接。
5. 老板核对明细，输入本店 boss 密码并批准。
6. 员工端状态应更新为已完成，PDF 和 Excel 归档生成。老板手机也可下载该笔 PDF。
7. 最后员工在真实 WhatsApp Web 中核对回复回填和附件发送。

第一次真实试验优先使用双方知情的自编演示询价。

## 五、状态怎么判断

| 状态 | 处理 |
| --- | --- |
| 等待启动手机模式 | 通知尚未提交给 WhatsApp；运行手机模式并保持窗口打开 |
| 通知已排队 / 正在提交 | 等待后台处理，界面会自动更新 |
| WhatsApp 接口已受理 | 只证明接口接受请求；请核对老板手机实际收件 |
| 接口返回失败 | 查看错误码，检查令牌、号码、模板和服务窗口；修正后再重试 |
| 发送结果不确定 | 先核对老板是否收到，再明确决定重发，避免重复通知 |
| 链接过期或报价已修改 | 生成最新版本的审批链接 |
| 手机服务暂未连接 | 保持电脑、手机入口和隧道运行，再检查最新 HTTPS 地址 |

当前没有接入送达 / 已读 webhook，所以不会把接口受理显示成已送达。进程中断时，正在发送的通知会标记为结果不确定，不会自动重复发送。

## 六、数据与代码

凭据保存在本机 data 下的连接设置文件，未采用硬件密钥库加密。不要把 data 文件夹分享给队友或上传 GitHub；分享本次源码压缩包即可。备份时先停服务，再完整备份 data，以保留账号、记录和手机链接签名信息。

新代码主要在 backend/ai.py、connections.py、mobile.py、mobile_gateway.py 和 mobile 文件夹。普通用户无需阅读这些文件。

开发验证命令和已完成范围在 VERIFICATION.md。包含的测试提供者只在 tests/mobile_fixture_server.py 中，由测试脚本显式启动，不参与 run.py 的真实运行，也不会使用真实凭据。

## 官方接口参考

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [WhatsApp service messages](https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/send-messages)
- [WhatsApp template fundamentals](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/overview)
- [WhatsApp template components](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/components/)
- [Meta Graph API changelog](https://developers.facebook.com/docs/graph-api/changelog/)
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

文档核对日期：2026 年 10 月 20 日。Meta 部分页在当前资料读取环境中无法完整打开，模板请求结构也参照了其官方历史 SDK 的文档；实际账号的权限、模板校验及消息送达仍需真实联调确认。
