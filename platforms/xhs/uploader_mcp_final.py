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

    async def check_login_status(self):
        """Check Xiaohongshu login status"""
        try:
            await self._ensure_session()

            # Call the tool using MCP SDK
            result = await self.session.call_tool("check_login_status", arguments={})

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
                            is_logged_in = "true" in text.lower() or "logged in" in text.lower()
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

            # Check login
            is_logged_in = await self.check_login_status()
            if not is_logged_in:
                self.logger.error("User not logged in")
                return False

            # DON'T convert to absolute path - the video is on the remote MCP server
            # The path should be used as-is (Windows path for Windows server)
            self.logger.info(f"Using video path: {video_path}")
            self.logger.info(f"Using tags (Chinese-only, max 10): {tags}")

            # Prepare arguments for publish_with_video tool
            arguments = {
                "title": video_name[:20],  # XHS 20 char limit
                "content": description or "",
                "video": video_path,  # Use path as-is for remote server
                "tags": tags
            }

            self.logger.info(f"Publishing video: {video_path}")

            # Call the tool using MCP SDK with longer timeout
            try:
                result = await asyncio.wait_for(
                    self.session.call_tool("publish_with_video", arguments=arguments),
                    timeout=900.0  # 15 minutes timeout for video upload
                )
            except asyncio.TimeoutError:
                self.logger.error("Upload timed out after 15 minutes")
                return False

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
