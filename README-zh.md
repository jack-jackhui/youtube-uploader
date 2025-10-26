<div align="center">

<h1 align="center">📹 AI视频上传工具 - 支持YouTube、Instagram和中国平台（小红书、抖音等）</h1>

<h3><a href="README.md">English</a> | 简体中文</h3>

</div>

---

## 项目介绍

本项目自动化视频生成并上传到多个平台：

- YouTube（Data API v3）
- Instagram Reels（Graph API）
- 中文平台：小红书（XHS）、抖音、头条
- 可选的AI视频主题和脚本生成

新功能：通过MCP（模型上下文协议）原生支持小红书上传，使用官方MCP SDK和开源的xiaohongshu-mcp服务器。

参考：https://github.com/xpzouying/xiaohongshu-mcp

---

## 核心功能

- YouTube和Instagram的OAuth 2.0认证
- 自动化视频生成流水线（主题 → 脚本 → 语音 → 渲染）
- 上传到YouTube、Instagram和中国平台
- 通过MCP SDK上传小红书（快速、可靠、兼容Claude传输协议）
- 基于环境的配置（.env.development，.env.production）
- 上传成功后的邮件通知

---

## 快速开始

- 推荐Python 3.10+
- 支持macOS、Windows或Linux

安装Python依赖：

```bash
pip install -r requirements.txt
```

如果计划使用非MCP浏览器自动化上传，安装Playwright浏览器（可选）：

```bash
python -m playwright install chromium
```

---

## 配置说明

本项目根据`ENV`环境变量使用不同的配置文件：

- `.env.development`（默认）
- `.env.production`

通过导出`ENV`来设置要加载的文件：

```bash
# macOS/Linux
export ENV=production
# Windows (PowerShell)
$env:ENV = "production"
```

### 通用设置

- OPEN_AI_KEY
- IG_USER_ID, IG_ACCESS_TOKEN（Instagram上传）
- SMTP凭证（如果使用邮件通知）

参考`example.env`获取指导，并将值复制到`.env.development`或`.env.production`。

### 小红书MCP设置（MCP模式必需）

在环境文件中添加这些设置或在运行前导出：

- `XHS_MCP_ENABLED=true` — 启用小红书MCP模式
- `XHS_MCP_SERVER_URL=http://<mcp-host>:18060/mcp` — MCP HTTP端点
- `HEADLESS=false` — 可选；如果为`false`，浏览器自动化可以显示浏览器窗口

**重要说明**：如果您的Python脚本和MCP服务器运行在**同一台电脑**上（大多数情况），您**不需要**设置`XHS_MCP_VIDEO_DIR`。视频会下载到本地`downloaded_videos`文件夹，MCP服务器可以直接访问相同的路径。

Windows示例（脚本和MCP在同一台电脑）：

```bat
set "XHS_MCP_ENABLED=true"
set "XHS_MCP_SERVER_URL=http://localhost:18060/mcp"
```

macOS/Linux示例：

```bash
export XHS_MCP_ENABLED=true
export XHS_MCP_SERVER_URL=http://localhost:18060/mcp
```

---

## 使用方法

在项目根目录：

```bash
# 英文视频：生成 + YouTube + Instagram（取决于环境标志）
python main.py --language en

# 中文视频：生成 + 上传到中国平台（如果启用MCP则通过MCP上传小红书）
python main.py --language zh
```

Windows用户的中文上传辅助脚本（默认使用MCP并正确映射路径）：

- `run_cn.bat` 设置所需的环境变量并运行 `python main.py --language zh`

---

## 小红书通过MCP上传

本项目使用官方MCP Python SDK与xiaohongshu-mcp服务器集成。

工作原理：

1. 应用生成您的视频
2. 如果启用MCP模式，视频会下载到本地`downloaded_videos`文件夹
3. 上传器使用本地文件路径调用MCP工具`publish_with_video`
4. MCP服务器（在同一台电脑上）自动化小红书网页上传

### MCP服务器设置（概述）

- 部署服务器：https://github.com/xpzouying/xiaohongshu-mcp
- 调试时使用`headless=false`启动以查看浏览器
- 在该浏览器会话中登录小红书一次
- 确认服务器可在`http://<host>:18060/mcp`访问

### 验证登录状态

运行MCP测试脚本（路径必须在本地存在）：

```bash
python test_mcp_upload.py "C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos\\example.mp4"
```

脚本将：

- 连接到MCP服务器
- 验证登录（`check_login_status`）
- 尝试使用`publish_with_video`发布

### 小红书MCP故障排除

- **浏览器不可见**：确保MCP服务器使用`headless=false`启动
- **"上传按钮不存在"**：使用`headless=false`启动并观察自动化；MCP服务器端的元素定位器可能需要更新
- **上传速度慢（比手动慢得多）**：确保MCP主机具有良好的网络和磁盘性能。由于脚本和MCP在同一台电脑上，文件已经在本地。禁用VPN/代理，并在非高峰时段尝试
- **超时**：我们的客户端使用15分钟的发布超时。如果您的网络很慢，可以在`platforms/xhs/uploader_mcp_final.py`中增加超时时间

---

## 依赖说明

我们调整了依赖版本以使MCP SDK与httpx/anyio/pydantic对齐：

- httpx：`>=0.27.1,<0.28`
- anyio：`>=4.6,<5`
- mcp SDK：`>=1.16.0,<2.0`
- pydantic：`>=2.10.1,<3`

安装：

```bash
pip install -r requirements.txt
```

如果您的非MCP上传器使用Playwright，安装Chromium运行时：

```bash
python -m playwright install chromium
```

---

## 项目结构（简化版）

- `main.py` — 编排生成和上传；如果启用MCP则映射路径
- `main_cn.py` — 中文平台的异步上传入口
- `platforms/xhs/uploader_mcp_final.py` — 使用官方SDK的基于MCP的小红书上传器
- `test_mcp_upload.py` — MCP上传的测试工具
- `run_cn.bat` — Windows辅助脚本运行中文/MCP工作流
- `downloaded_videos/` — 本地下载（非MCP）或中间文件

---

## 安全与最佳实践

- 不要提交`.env.*`文件或密钥
- 使用单独的`.env.development`和`.env.production`
- 定期轮换API密钥

---

## 致谢

- Google YouTube Data API、Facebook Graph API
- 中文平台上传器参考：https://github.com/aceliuchanghong/bili_douyin_xhs_uploader
- 小红书MCP服务器：https://github.com/xpzouying/xiaohongshu-mcp

---

## 许可证

MIT。详见[LICENSE](LICENSE)。

