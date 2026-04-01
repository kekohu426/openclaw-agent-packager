# OpenClaw Agent Packager

一个面向 **OpenClaw agent 交付与迁移** 的可复用 skill。

它的目标不是“把文件压缩一下”，而是把一个或多个已经跑通的 agent，整理成 **客户可安装、可迁移、可验证** 的交付包，适用于：

- 单 agent 交付
- 多 agent 组合交付
- 从一套 OpenClaw 迁移到另一套 OpenClaw
- Windows 环境下的客户安装与实施
- 内部迁移测试
- 后续可扩展为对外脱敏交付

## 这个 skill 能做什么

- 支持 **单 agent** 打包
- 支持 **多 agent** 打包
- 默认 **瘦身打包**，排除运行时垃圾
- 可选 `--include-memory` 携带 `memory/`
- 自动生成交付文件：
  - `README.md`
  - `CHECK.ps1`
  - `INSTALL.ps1`
  - `manifest.json`
  - `customer-settings.template.json`
- 自动打包每个 agent 的 workspace
- 自动整理 `models.json` / `auth-profiles.json`
- 自动合并目标 OpenClaw 配置中的必要字段
- 支持 Feishu 迁移后的 pairing 流程说明

## 为什么需要它

很多人在本机把 agent 调通之后，真正困难的不是 agent 本身，而是交付：

- 客户机器的 OpenClaw 路径不一样
- 本地 workspace 不能直接照搬
- 多个 agent 同时迁移时，配置容易互相污染
- Feishu 机器人迁移后可能提示 `access not configured`
- 客户不可能自己去理解每个配置字段

这个 skill 的核心思路是：

- **不整份覆盖 `openclaw.json`**
- **只合并必要字段**
- **生成客户可执行的安装包**
- **把容易踩坑的 pairing 流程写进包里**

## 安全边界

默认不会把整个运行环境都打进去。

会主动排除这些内容：

- `sessions`
- `.openclaw`
- `node_modules`
- 缓存目录
- 日志
- 大图片和临时产物
- 常见运行时垃圾

默认也 **不会自动携带 `memory/`**，只有显式加 `--include-memory` 才会带上。

## 仓库结构

```text
openclaw-agent-packager/
├─ SKILL.md
├─ README.md
├─ references/
│  └─ package-layout.md
└─ scripts/
   └─ build_package.py
```

## 生成后的安装包结构

```text
<package-name>/
├─ README.md
├─ INSTALL.ps1
├─ CHECK.ps1
├─ manifest.json
├─ customer-settings.template.json
├─ configs/
│  ├─ openclaw.fragment.json
│  ├─ models.sanitized.json
│  └─ auth-profiles.sanitized.json
└─ workspaces/
   ├─ <agent-id-1>/
   └─ <agent-id-2>/
```

## 合并策略

这个 skill 不会粗暴复制整份源配置，而是只迁移这些必要内容：

- `agents.list` 中目标 agent 的条目
- `bindings`
- `channels.*.accounts.<agentId>`
- 每个 agent 的 workspace
- 每个 agent 的 `models.json`
- 每个 agent 的 `auth-profiles.json`（如果有）

这样做的目的是尽量降低对目标 OpenClaw 环境的破坏性。

## 快速开始

### 1) 单 agent 打包

```powershell
python scripts/build_package.py \
  --source-openclaw "C:\Users\you\.openclaw" \
  --workspace-root "C:\Users\you\clawd" \
  --agents sysmon \
  --output-dir "C:\Users\you\Desktop" \
  --package-name "openclaw-delivery-sysmon" \
  --target-openclaw "D:\openclaw\latest\data\.openclaw" \
  --zip
```

### 2) 多 agent 打包

```powershell
python scripts/build_package.py \
  --source-openclaw "C:\Users\you\.openclaw" \
  --workspace-root "C:\Users\you\clawd" \
  --agents intel homework-analyzer \
  --output-dir "C:\Users\you\Desktop" \
  --package-name "openclaw-delivery-suite" \
  --target-openclaw "D:\openclaw\latest\data\.openclaw" \
  --zip
```

### 3) 带 memory 打包

```powershell
python scripts/build_package.py \
  --source-openclaw "C:\Users\you\.openclaw" \
  --workspace-root "C:\Users\you\clawd" \
  --agents sysmon \
  --output-dir "C:\Users\you\Desktop" \
  --package-name "openclaw-delivery-sysmon-with-memory" \
  --target-openclaw "D:\openclaw\latest\data\.openclaw" \
  --include-memory \
  --zip
```

### 4) 对外脱敏包

如果是发给客户或外部环境，建议使用：

```powershell
python scripts/build_package.py \
  --source-openclaw "C:\Users\you\.openclaw" \
  --workspace-root "C:\Users\you\clawd" \
  --agents sysmon \
  --output-dir "C:\Users\you\Desktop" \
  --package-name "openclaw-delivery-sysmon-external" \
  --target-openclaw "D:\openclaw\latest\data\.openclaw" \
  --external \
  --zip
```

`--external` 会把 channel account 中的敏感值改成占位符，避免直接把密钥跟着安装包发出去。

## 客户安装流程

客户拿到压缩包后，一般只需要按下面顺序操作：

### 1) 解压

把交付包解压到任意目录。

### 2) 检查安装包结构

```powershell
powershell -ExecutionPolicy Bypass -File .\CHECK.ps1
```

### 3) 首次运行安装脚本

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1
```

如果 `customer-settings.json` 不存在，脚本会自动从模板生成一份。

### 4) 如有需要，调整 `customer-settings.json`

主要包括：

- `targetOpenClaw`
- 每个 agent 的 workspace 路径
- 模型 provider 的 key
- auth profile 的 key
- 外发模式下的 channel account secret

### 5) 再次执行安装并重启网关

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1 -RestartGateway
```

## Feishu pairing 说明

这是客户最容易误判的一步。

如果迁移后的 Feishu 机器人第一次回复：

```text
OpenClaw: access not configured.
```

这通常 **不是安装失败**，而是当前发消息的用户还没有完成 pairing。

### 客户要做什么

1. 在飞书里给机器人发一条消息
2. 机器人返回：
   - `Your Feishu user id`
   - `Pairing code`
3. 把 `Pairing code` 发给管理员/交付方

### 管理员要做什么

在目标 OpenClaw 所在机器上执行：

```powershell
openclaw pairing approve feishu <PAIRING_CODE>
```

执行完成后，再次给机器人发消息即可。

## manifest.json 的用途

`manifest.json` 不只是记录包名，它也会记录：

- 打包了哪些 agent
- 是否带了 memory
- 每个 agent 实际带了哪些 workspace 文件
- 是否存在 warning

例如：

- 源配置里声明了 workspace
- 但本地目录实际上不存在

这种情况下，脚本不会直接失败，而会把 warning 写进 `manifest.json`，方便交付时排查。

## 已验证的真实场景

这个 skill 已经做过真实迁移验证，包括：

- 单 agent 打包与迁移
- 多 agent 打包与迁移
- 目标 OpenClaw 配置合并
- D 盘最新 OpenClaw 环境加载
- Feishu WebSocket 启动
- pairing 授权后恢复可用

## 已知注意事项

- 如果源 workspace 目录不存在，打包仍可继续，但 `manifest.json` 会出现 warning
- 某些网关重启命令可能执行成功，但终端返回较慢，建议结合日志一起判断
- 内部迁移模式适合受控环境；对外发包建议优先使用 `--external`
- 如果目标环境是 Feishu，安装文档里一定要写 pairing 流程

## 如何把它作为 skill 使用

把整个目录放进你的 Codex skills 目录，例如：

```text
$CODEX_HOME/skills/openclaw-agent-packager/
```

然后在需要时触发它，用于：

- 打包 agent
- 做单 agent / 多 agent 迁移
- 生成客户安装包
- 交付 OpenClaw 机器人

## 公众号与联系

如果你对这类内容感兴趣，我会持续分享：

- OpenClaw agent 打包与交付
- 单 agent / 多 agent 迁移实战
- Feishu pairing 排障
- 自动化安装与部署经验

欢迎关注公众号：**娇姐话AI圈**

如果你需要进一步交流或合作，也可以加我微信：**kekohu**

## License

当前仓库尚未附带 License。

如果你准备公开推广，建议至少补一个：

- `MIT`
- 或 `Apache-2.0`

## 后续计划

- 补充更清晰的外发脱敏包说明
- 增加 pairing 专项说明文档
- 补充 GitHub 示例与 FAQ
- 优化非技术客户的安装体验
