<div align="center">

<h1 align="center">📹 AI Video Uploader for YouTube, Instagram, and Chinese Platforms (XHS/小红书, Douyin, etc.)</h1>

<h3>English | <a href="README-zh.md">简体中文</a></h3>

</div>

---

## Introduction

This project automates video generation and uploading to multiple platforms:

- YouTube (Data API v3)
- Instagram Reels (Graph API)
- Chinese platforms: Xiaohongshu/小红书 (XHS), Douyin, Toutiao
- Optional AI generation for video topics and scripts

New: Native support for Xiaohongshu uploads via MCP (Model Context Protocol) using the official MCP SDK and the open-source xiaohongshu-mcp server.

Reference: https://github.com/xpzouying/xiaohongshu-mcp

---

## Key Features

- OAuth 2.0 for YouTube and Instagram
- Automated video generation pipeline (topic → script → voice → render)
- Upload to YouTube, Instagram, and Chinese platforms
- Xiaohongshu (XHS) via MCP SDK (fast, reliable, Claude-compatible transport)
- Environment-based configuration (.env.development, .env.production)
- Email notifications on successful uploads

---

## Quick Start

- Python 3.10+ recommended
- macOS, Windows, or Linux

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install Playwright browsers if you plan to upload via non-MCP browser automation (optional):

```bash
python -m playwright install chromium
```

---

## Configuration

This project uses separate env files based on `ENV`:

- `.env.development` (default)
- `.env.production`

Set which file to load by exporting `ENV`:

```bash
# macOS/Linux
export ENV=production
# Windows (PowerShell)
$env:ENV = "production"
```

### Common Settings

- OPEN_AI_KEY
- IG_USER_ID, IG_ACCESS_TOKEN (Instagram Upload)
- SMTP credentials if using email notifications

See `example.env` for guidance and copy values into `.env.development` or `.env.production`.

### Xiaohongshu MCP Settings (Required for MCP mode)

Add these to your env file or export them before running:

- `XHS_MCP_ENABLED=true` — enable MCP mode for XHS
- `XHS_MCP_SERVER_URL=http://<mcp-host>:18060/mcp` — MCP HTTP endpoint
- `XHS_MCP_VIDEO_DIR=...` — absolute directory path on the MCP server where videos are stored
- `HEADLESS=false` — optional; if `false`, non-MCP browser automation can show a browser window

Example (Windows MCP host):

```bat
set "XHS_MCP_ENABLED=true"
set "XHS_MCP_SERVER_URL=http://192.168.1.9:18060/mcp"
set "XHS_MCP_VIDEO_DIR=C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos\\pending_upload"
```

Example (macOS/Linux shell):

```bash
export XHS_MCP_ENABLED=true
export XHS_MCP_SERVER_URL=http://192.168.1.9:18060/mcp
export XHS_MCP_VIDEO_DIR="/mnt/shared/pending_upload"  # path as seen by the MCP server
```

Important: `XHS_MCP_VIDEO_DIR` must be a path that exists on the MCP server host. The app downloads the generated video directly into that folder so the MCP server can access it instantly.

---

## Usage

From the project root:

```bash
# English video: generate + YouTube + Instagram (depending on env flags)
python main.py --language en

# Chinese video: generate + upload to Chinese platforms (XHS via MCP if enabled)
python main.py --language zh
```

Windows helper for Chinese uploads (uses MCP by default and maps paths correctly):

- `run_cn.bat` sets the required env vars and runs `python main.py --language zh`.

---

## Xiaohongshu (XHS/小红书) via MCP

This project integrates with the xiaohongshu-mcp server using the official MCP Python SDK.

How it works:

1. The app generates your video.
2. If MCP mode is enabled, the video is downloaded directly into `XHS_MCP_VIDEO_DIR` (a folder on the MCP server host).
3. The uploader calls the MCP tool `publish_with_video` with the server-side file path.
4. The MCP server automates the XHS web upload.

### MCP Server Setup (Summary)

- Deploy the server: https://github.com/xpzouying/xiaohongshu-mcp
- Start it with `headless=false` during debugging to see the browser.
- Log in to Xiaohongshu once in that browser session.
- Confirm the server is reachable at `http://<host>:18060/mcp`.

### Verifying Login

Run the MCP test script (path must exist on the MCP server):

```bash
python test_mcp_upload.py "C:\\Users\\jack\\Python-Apps\\youtube-uploader\\downloaded_videos\\pending_upload\\example.mp4"
```

The script will:

- Connect to the MCP server
- Verify login (`check_login_status`)
- Attempt a publish using `publish_with_video`

### Troubleshooting XHS MCP

- Browser not visible: ensure the MCP server was started with `headless=false`.
- "Upload button not present": start with `headless=false` and watch the automation; element locators may need updating on the MCP server side.
- Slow upload (much slower than manual): ensure the MCP host has good network and disk performance. Keep the video file on the same machine (we already do by writing into `XHS_MCP_VIDEO_DIR`). Disable VPN/Proxy and try during off-peak hours.
- Timeout: our client uses a 15-minute publish timeout. If your network is slow, increase it in `platforms/xhs/uploader_mcp_final.py` if needed.

---

## Dependency Notes

We adjusted dependency versions to align the MCP SDK with httpx/anyio/pydantic:

- httpx: `>=0.27.1,<0.28`
- anyio: `>=4.6,<5`
- mcp SDK: `>=1.16.0,<2.0`
- pydantic: `>=2.10.1,<3`

Install:

```bash
pip install -r requirements.txt
```

If Playwright is used by your non-MCP uploaders, install the Chromium runtime:

```bash
python -m playwright install chromium
```

---

## Project Structure (Simplified)

- `main.py` — orchestrates generation and uploads; maps paths for MCP if enabled
- `main_cn.py` — async upload entry for Chinese platforms
- `platforms/xhs/uploader_mcp_final.py` — MCP-based XHS uploader using official SDK
- `test_mcp_upload.py` — test harness for MCP upload
- `run_cn.bat` — Windows helper to run Chinese/MCP workflow
- `downloaded_videos/` — local downloads (non-MCP) or intermediate files

---

## Security & Best Practices

- Do not commit `.env.*` files or secrets
- Use separate `.env.development` and `.env.production`
- Rotate API keys regularly

---

## Acknowledgements

- Google YouTube Data API, Facebook Graph API
- Chinese platform uploader references from https://github.com/aceliuchanghong/bili_douyin_xhs_uploader
- Xiaohongshu MCP server: https://github.com/xpzouying/xiaohongshu-mcp

---

## License

MIT. See [LICENSE](LICENSE).
