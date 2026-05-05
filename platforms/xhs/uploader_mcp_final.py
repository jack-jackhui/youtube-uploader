#!/usr/bin/env python3
"""
MCP uploader using official MCP SDK with streamable HTTP transport
This is the correct way to connect to xiaohongshu-mcp server (same as Claude Desktop)
"""
import json
import os
import asyncio
import re
from datetime import datetime
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from core import config
from core.upload import Upload
from utils.util_sqlite import excute_sqlite_sql


class XhsMcpUploader(Upload):
    """
    MCP uploader using official SDK with streamable HTTP transport
    Compatible with xiaohongshu-mcp server
    """
    platform = "xhs_mcp"

    def __init__(self):
        super().__init__()

        self.mcp_server_url = os.getenv('XHS_MCP_SERVER_URL', 'http://192.168.1.9:18060/mcp')
        self.mcp_enabled = os.getenv('XHS_MCP_ENABLED', 'false').lower() == 'true'
        # MCP supports: 公开可见 / 仅自己可见 / 仅互关好友可见.
        # Default automated MCP uploads to private.
        self.visibility = os.getenv('XHS_MCP_VISIBILITY', '仅自己可见')

        if not self.mcp_enabled:
            raise ValueError("XHS MCP is not enabled. Set XHS_MCP_ENABLED=true in environment variables.")

        if not self.mcp_server_url.startswith(('http://', 'https://')):
            self.mcp_server_url = f"http://{self.mcp_server_url}"

        self.logger.info(f"Initialized XhsMcpUploader with URL: {self.mcp_server_url}")
        self.session = None
        self.client_context = None
        self.session_context = None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures proper cleanup"""
        await self._cleanup_session()

    def __del__(self):
        """Destructor to ensure cleanup on object deletion"""
        if self.session is not None:
            try:
                import asyncio
                # Only cleanup if we're in an async context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule cleanup as a task
                    loop.create_task(self._cleanup_session())
            except:
                # If no event loop or other issues, just reset the references
                self.session = None
                self.session_context = None
                self.client_context = None

    async def _ensure_session(self):
        """Ensure MCP session is initialized"""
        if self.session is not None:
            return

        self.logger.info("Connecting to MCP server via streamable HTTP...")

        # Create streamable HTTP client (like Claude Desktop does)
        self.client_context = streamablehttp_client(self.mcp_server_url)
        read_stream, write_stream, _ = await self.client_context.__aenter__()

        # Create client session
        self.session_context = ClientSession(read_stream, write_stream)
        self.session = await self.session_context.__aenter__()

        # Initialize the connection
        await self.session.initialize()

        self.logger.info("✅ MCP session initialized successfully")

    async def _cleanup_session(self):
        """Cleanup MCP session properly to avoid asyncio errors"""
        if self.session:
            try:
                # Close the session first
                await self.session.close()
            except Exception as e:
                self.logger.debug(f"Session close error (non-critical): {e}")
        
        if self.session_context:
            try:
                await self.session_context.__aexit__(None, None, None)
            except Exception as e:
                self.logger.debug(f"Session context cleanup error (non-critical): {e}")
        
        if self.client_context:
            try:
                await self.client_context.__aexit__(None, None, None)
            except Exception as e:
                self.logger.debug(f"Client context cleanup error (non-critical): {e}")
        
        # Reset all session objects
        self.session = None
        self.session_context = None
        self.client_context = None

    async def _call_tool_with_timeout(self, tool_name: str, arguments: dict, timeout: float = 180.0):
        """
        Call MCP tool with extended timeout for slow browser operations on Windows scheduled runs.

        Args:
            tool_name: Name of the MCP tool to call
            arguments: Tool arguments
            timeout: Timeout in seconds (default 180s for cold-start, 900s for uploads)

        Returns:
            Tool result or None if timeout occurs
        """
        try:
            return await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments=arguments),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                f"⚠️  MCP call '{tool_name}' timed out after {timeout}s - "
                f"this may indicate slow browser initialization on Windows scheduled runs. "
                f"Consider increasing timeout if this persists."
            )
            raise

    async def check_login_status(self):
        """Check Xiaohongshu login status"""
        try:
            await self._ensure_session()

            # Call the tool using MCP SDK with timeout for cold-start browser operations
            result = await self._call_tool_with_timeout(
                "check_login_status",
                arguments={},
                timeout=180.0  # 3 minutes for login check (includes cold-start browser init)
            )

            # Parse response
            if result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        text = content_item.text

                        # Parse the response
                        try:
                            status_data = json.loads(text)
                            is_logged_in = status_data.get("IsLoggedIn", False) or status_data.get("is_logged_in", False)
                            username = status_data.get("Username", "") or status_data.get("username", "")
                        except json.JSONDecodeError:
                            # Plain text response
                            is_logged_in = "true" in text.lower() or "logged in" in text.lower() or "已登录" in text or "✅" in text
                            username = "Unknown"

                        if is_logged_in:
                            self.logger.info(f"✅ Logged in as: {username}")
                        else:
                            self.logger.warning("❌ Not logged in")

                        return is_logged_in

            self.logger.error("Invalid response format")
            return False

        except Exception as e:
            self.logger.error(f"Failed to check login status: {e}")
            return False

    async def _warm_up_login(self, max_retries: int = 3):
        """Warm MCP/browser by checking login with retry, matching xhs_publish.py."""
        for attempt in range(max_retries):
            if await self.check_login_status():
                return True
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                self.logger.warning(f"MCP login warm-up failed; retrying in {wait}s ({attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
        return False

    async def _call_publish_with_retries(self, arguments: dict, max_retries: int = 3):
        """Publish with retry/backoff for slow Windows MCP/browser operations."""
        for attempt in range(max_retries):
            try:
                self.logger.info(f"MCP publish attempt {attempt + 1}/{max_retries}")
                return await self._call_tool_with_timeout(
                    "publish_with_video",
                    arguments=arguments,
                    timeout=900.0
                )
            except Exception as exc:
                if attempt < max_retries - 1:
                    wait = 30 * (attempt + 1)
                    self.logger.warning(f"MCP publish attempt failed: {exc}; retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise

    def _build_tags(self, topics):
        """Build Chinese-only tags for XHS.
        - Keep at most 2 user-provided tags containing Chinese characters and no Latin letters
        - Append predefined Chinese keywords from config
        - Deduplicate while preserving order
        - Cap the total number of tags (default 10, configurable via XHS_MAX_TAGS)
        """
        max_tags = int(os.getenv("XHS_MAX_TAGS", "10"))

        def is_chinese_only(s: str) -> bool:
            if not isinstance(s, str):
                return False
            t = s.strip()
            if not t:
                return False
            # has CJK
            has_cjk = re.search(r"[\u3400-\u9fff\uf900-\ufaff]", t) is not None
            # reject if contains Latin letters
            has_latin = re.search(r"[A-Za-z]", t) is not None
            return has_cjk and not has_latin

        user_cn = []
        seen = set()
        # take up to 2 chinese-only from input topics
        for tag in (topics or []):
            if len(user_cn) >= 2:
                break
            if not isinstance(tag, str):
                continue
            candidate = tag.strip()
            if not candidate:
                continue
            if is_chinese_only(candidate) and candidate not in seen:
                user_cn.append(candidate)
                seen.add(candidate)

        # append predefined chinese keywords
        predefined = []
        for k in getattr(config, 'keywords', []) or []:
            if isinstance(k, str):
                kk = k.strip()
                if kk and is_chinese_only(kk) and kk not in seen:
                    predefined.append(kk)
                    seen.add(kk)

        final = user_cn + predefined
        # cap
        if len(final) > max_tags:
            final = final[:max_tags]
        return final

    async def upload_video(self, video_url, video_path, video_name, cover_path=None,
                          description=None, topics=None, collection=None, headless=False):
        """Upload video to Xiaohongshu via MCP"""
        if topics is None:
            topics = []
        # Build Chinese-only tags per XHS rules
        tags = self._build_tags(topics)

        try:
            await self._ensure_session()

            self.logger.info(f"Uploading video '{video_name}' via MCP...")

            # Warm up/check login before publishing (same robust pattern as xhs_publish.py).
            is_logged_in = await self._warm_up_login()
            if not is_logged_in:
                self.logger.error("User not logged in")
                return False

            # DON'T convert to absolute path - the video is on the remote MCP server
            # The path should be used as-is (Windows path for Windows server)
            self.logger.info(f"Using video path: {video_path}")
            self.logger.info(f"Using tags (Chinese-only, max 10): {tags}")
            self.logger.info(f"Using visibility: {self.visibility}")

            # Prepare arguments for publish_with_video tool. MCP schema confirms
            # video must be a local absolute path on the MCP server/browser
            # machine, so we pass the SMB-converted Windows path.
            arguments = {
                "title": video_name[:20],  # XHS 20 char limit
                "content": description or "",
                "video": video_path,
                "tags": tags,
                "visibility": self.visibility
            }

            self.logger.info(f"Publishing video: {video_path}")

            # Call the tool using robust retry/backoff for video upload.
            result = await self._call_publish_with_retries(arguments)

            # Parse response
            if result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        text = content_item.text

                        # Check for success
                        success = "成功" in text or "success" in text.lower()

                        if success:
                            self.logger.info("✅ Video published successfully!")

                            # Save to database
                            try:
                                excute_sqlite_sql(
                                    config.table_add_sql,
                                    (self.platform, video_name, datetime.now().strftime('%Y%m%d'),
                                     video_url, video_path, collection, description)
                                )
                                self.logger.info("Record saved to database")
                            except Exception as db_err:
                                self.logger.warning(f"Database save failed: {db_err}")

                            return True
                        else:
                            self.logger.error(f"Upload failed: {text}")
                            return False

            self.logger.error("Invalid response format")
            return False

        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            import traceback
            traceback.print_exc()
            return False
        # DON'T cleanup session here - keep it alive for next upload
