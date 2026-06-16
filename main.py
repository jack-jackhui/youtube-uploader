# main.py
"""
AI Video Pipeline - Generates and uploads videos to YouTube, Instagram, and Chinese platforms.

Safety: Videos are uploaded as PRIVATE by default. Set YOUTUBE_DEFAULT_PRIVACY=public to change.
Compliance: Pre-upload checks run automatically. Set COMPLIANCE_STRICT_MODE=true for stricter checks.
"""

import asyncio
import argparse
import json
import re
import sys
from pathlib import Path
import video_api_call
from youtube_manager import authenticate_youtube, upload_video, update_video_privacy
from voice_manager import get_last_used_voice, get_random_voice, store_last_used_voice
from video_manager import generate_video_subject, process_video_subject, generate_video_and_get_urls
from dotenv import load_dotenv
import os
from smb_path_helper import get_download_path, linux_to_windows_path
from email_notifier import send_email
from instagram_publisher import publish_video_to_instagram
from main_cn import main as chinese_uploader_main
from error_reporter import report_error, report_success, create_run_summary
from compliance_gate import check_before_upload, ComplianceResult

# Safe background music mixer (generated locally to avoid random third-party BGM claims)
try:
    from safe_background_music import add_safe_background_music
    SAFE_BGM_AVAILABLE = True
except ImportError:
    SAFE_BGM_AVAILABLE = False
    print("[main.py] Safe BGM module not available - uploads will keep source audio only")

# Auto-publish checker (optional - checks processing status and auto-publishes if clean)
try:
    from auto_publish_checker import AutoPublishChecker
    AUTO_PUBLISH_AVAILABLE = True
except ImportError:
    AUTO_PUBLISH_AVAILABLE = False
    print("[main.py] Auto-publish checker not available")

# CTA Overlay module (optional - graceful fallback if not available)
try:
    from cta_overlay import process_video_with_overlay, OverlayConfig
    CTA_OVERLAY_AVAILABLE = True
except ImportError:
    CTA_OVERLAY_AVAILABLE = False
    print("[main.py] CTA overlay module not available - overlays disabled")

# Determine which .env file to load
env = os.getenv("ENV", "development")
dotenv_path = f".env.{env}"
load_dotenv(dotenv_path=dotenv_path)

# Environment variables
api_host = os.getenv("API_HOST")
api_key = os.getenv("API_KEY")
openai_api_key = os.getenv("OPEN_AI_KEY")
ig_user_id = os.getenv("IG_USER_ID")
ig_access_token = os.getenv("IG_ACCESS_TOKEN")

print(f"[main.py] Starting up (env={env})")


def _clean_hashtag(tag):
    return str(tag).strip().lstrip("#")


def _extract_markdown_section(text, heading):
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    match = re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], flags=re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def _parse_markdown_script(path):
    text = Path(path).read_text(encoding="utf-8")
    metadata = {"source": str(path)}
    title = ""
    suggested = re.search(r"^##\s+Suggested Title\s*\n+(.+?)\s*(?:\n##|\Z)", text, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
    if suggested:
        title = suggested.group(1).strip().splitlines()[0].strip()
    if not title:
        heading = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        if heading:
            title = re.sub(r"^Day\s+\d+\s+[—-]\s+", "", heading.group(1).strip(), flags=re.IGNORECASE)
    if not title:
        title = Path(path).stem.replace("-", " ").replace("_", " ").title()
    voiceover = _extract_markdown_section(text, "Voiceover Script with Timing")
    quoted_lines = []
    for line in voiceover.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("**on-screen text:"):
            continue
        for item in re.findall(r"\*\*(.+?)\*\*", line):
            cleaned = item.strip().strip("“”\"'")
            if cleaned and not cleaned.lower().startswith("on-screen text:"):
                quoted_lines.append(cleaned)
    script = "\n\n".join(quoted_lines) or voiceover or text
    caption = _extract_markdown_section(text, "Caption")
    description = _extract_markdown_section(text, "Suggested YouTube Description") or caption
    hashtag_section = _extract_markdown_section(text, "Hashtags")
    hashtags = re.findall(r"#[\w-]+", hashtag_section)
    cta_match = re.search(r"\*\*CTA:\*\*\s*(.+)", text)
    if cta_match:
        metadata["cta"] = cta_match.group(1).strip()
    if description:
        metadata["description"] = description.strip()
    if caption:
        metadata["caption"] = caption.strip()
    if hashtags:
        metadata["hashtags"] = hashtags
    return {"topic": title, "script": script.strip(), "hashtags": hashtags, "metadata": metadata}


def _parse_json_script(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    topic = data.get("topic") or data.get("title") or data.get("video_subject")
    script = data.get("script") or data.get("video_script") or data.get("body") or data.get("voiceover")
    hashtags = data.get("hashtags") or data.get("tags") or []
    if isinstance(hashtags, str):
        hashtags = re.findall(r"#[\w-]+", hashtags) or [h.strip() for h in hashtags.split(",") if h.strip()]
    metadata = {k: v for k, v in data.items() if k not in ("script", "video_script", "body", "voiceover")}
    return {"topic": topic, "script": script, "hashtags": hashtags, "metadata": metadata}


def load_script_file(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return _parse_json_script(path)
    if suffix in (".md", ".markdown", ".txt"):
        return _parse_markdown_script(path)
    raise ValueError(f"Unsupported script file type: {suffix or 'unknown'}")


def _compose_backlog_script(entry):
    for key in ("script", "video_script", "full_script", "body", "voiceover"):
        value = entry.get(key)
        if value:
            return str(value).strip()
    parts = []
    if entry.get("hook"):
        parts.append(str(entry["hook"]).strip())
    if entry.get("script_outline"):
        outline = re.sub(r";\s*", "\n", str(entry["script_outline"]).strip())
        parts.append(outline)
    if entry.get("cta"):
        parts.append(str(entry["cta"]).strip())
    return "\n\n".join(part for part in parts if part)


def load_backlog_entry(path, day):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        videos = data.get("videos") or data.get("days") or data.get("entries") or []
        campaign_meta = {k: v for k, v in data.items() if k not in ("videos", "days", "entries")}
    else:
        videos = data
        campaign_meta = {}
    entry = None
    for candidate in videos:
        if int(candidate.get("day", -1)) == int(day):
            entry = candidate
            break
    if not entry:
        raise ValueError(f"No backlog entry found for day {day} in {path}")
    hashtags = entry.get("hashtags") or entry.get("tags") or []
    if isinstance(hashtags, str):
        hashtags = re.findall(r"#[\w-]+", hashtags) or [h.strip() for h in hashtags.split(",") if h.strip()]
    metadata = {**campaign_meta, **entry, "source": str(path)}
    return {"topic": entry.get("topic") or entry.get("title") or f"Campaign Day {day}", "script": _compose_backlog_script(entry), "hashtags": hashtags, "metadata": metadata}


def resolve_campaign_input(args):
    """Return optional campaign input while preserving legacy behavior when no new flags are used."""
    if args.backlog and args.day is None:
        raise ValueError("--day is required when --backlog is supplied")
    if args.day is not None and not args.backlog:
        raise ValueError("--backlog is required when --day is supplied")
    campaign_input = None
    if args.backlog:
        campaign_input = load_backlog_entry(args.backlog, args.day)
    elif args.script_file:
        campaign_input = load_script_file(args.script_file)
    elif args.topic:
        campaign_input = {"topic": args.topic, "script": None, "hashtags": [], "metadata": {}}
    if campaign_input and args.topic:
        campaign_input["topic"] = args.topic
    if campaign_input:
        campaign_input.setdefault("metadata", {})["campaign"] = args.campaign
    return campaign_input


def build_upload_description(video_subject, video_script, metadata):
    description = metadata.get("description") or metadata.get("caption") or video_script or video_subject
    cta = metadata.get("cta")
    utm_params = metadata.get("utm_params")
    hashtags = metadata.get("hashtags") or []
    chunks = [str(description).strip()]
    if cta and cta not in chunks[0]:
        chunks.append(str(cta).strip())
    if utm_params:
        campaign_name = str(metadata.get("campaign") or "").lower()
        if metadata.get("product_url"):
            base_url = metadata["product_url"]
            label = metadata.get("product_name") or metadata.get("campaign") or "Learn more"
        elif "selectprep" in campaign_name:
            base_url = "https://selectprep.com.au"
            label = "Try SelectPrep"
        else:
            base_url = "https://winning-cv.jackhui.com.au"
            label = "Try WinningCV"
        chunks.append(f"{label}: {base_url}?{utm_params}")
    if hashtags:
        chunks.append(" ".join(str(tag) for tag in hashtags))
    return "\n\n".join(chunk for chunk in chunks if chunk)


def tags_from_campaign(campaign_input, fallback_terms):
    tags = (campaign_input.get("hashtags") or []) if campaign_input else []
    cleaned = [_clean_hashtag(tag) for tag in tags if str(tag).strip()]
    return cleaned or fallback_terms or ["WinningCV", "resume", "jobsearch", "AI"]


def run_compliance_check(video_path, title, description, source_url, tags):
    """
    Run pre-upload compliance check.
    
    Returns:
        ComplianceResult with pass/fail status
    """
    print(f"\n[Compliance] Running pre-upload compliance check...")
    
    result = check_before_upload(
        video_path=video_path,
        title=title,
        description=description,
        source_url=source_url,
        tags=tags,
        strict=os.getenv("COMPLIANCE_STRICT_MODE", "false").lower() == "true"
    )
    
    if result.issues:
        print(f"[Compliance] FAILED - Issues found:")
        for issue in result.issues:
            print(f"  - {issue}")
    
    if result.warnings:
        print(f"[Compliance] Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
    
    if result.passed:
        print(f"[Compliance] Passed all checks")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate and upload videos to various platforms.")
    parser.add_argument("--language", choices=["en", "zh"], default="en", 
                       help="Language of the video")
    parser.add_argument("--script-file", help="Use a provided Markdown/JSON script and metadata file instead of generating the script internally")
    parser.add_argument("--topic", help="Use the provided topic as the video subject")
    parser.add_argument("--backlog", help="Load a campaign entry from a JSON video backlog")
    parser.add_argument("--day", type=int, help="Campaign day to load from --backlog")
    parser.add_argument("--campaign", default="default", help="Optional campaign name for metadata/reporting, e.g. winningcv")
    parser.add_argument("--validate-input-only", action="store_true", help="Validate campaign/script input and exit before video generation or uploads")
    parser.add_argument("--skip-compliance", action="store_true", help="Skip compliance checks (use with caution)")
    parser.add_argument("--publish-after-check", action="store_true", help="Publish video after manual compliance check (requires video_id)")
    parser.add_argument("--video-id", type=str, help="YouTube video ID for --publish-after-check")
    args = parser.parse_args()
    
    # Handle publish-after-check mode
    if args.publish_after_check:
        if not args.video_id:
            print("Error: --video-id required with --publish-after-check")
            return 1
        try:
            youtube = authenticate_youtube()
            update_video_privacy(youtube, args.video_id, "public")
            print(f"Video {args.video_id} is now PUBLIC")
            print(f"  URL: https://youtube.com/watch?v={args.video_id}")
            return 0
        except Exception as e:
            print(f"Error publishing video: {e}")
            return 1
    language = args.language
    campaign_input = resolve_campaign_input(args)
    if args.validate_input_only:
        if not campaign_input:
            print("[Validation] No campaign/script input supplied; legacy generation path would be used.")
            return 0
        metadata = campaign_input.get("metadata", {})
        tags = tags_from_campaign(campaign_input, None)
        description = build_upload_description(campaign_input.get("topic"), campaign_input.get("script"), metadata)
        print("[Validation] Campaign input OK")
        print(f"[Validation] Topic: {campaign_input.get('topic')}")
        print(f"[Validation] Script chars: {len(campaign_input.get('script') or '')}")
        print(f"[Validation] Tags: {', '.join(tags)}")
        print(f"[Validation] Description chars: {len(description)}")
        # Validate CTA overlay config if present
        overlay_config = metadata.get("cta_overlay", {})
        if overlay_config.get("enabled"):
            print(f"[Validation] CTA Overlay: enabled")
            print(f"[Validation] CTA Text: {overlay_config.get('text', '')} : {overlay_config.get('url', '')}")
        return 0
    
    # Track results for summary
    results = {
        "Video Generation": {"success": False},
        "Compliance Check": {"success": False, "skipped": False},
        "YouTube Upload": {"success": False, "skipped": False},
        "Instagram Upload": {"success": False, "skipped": False}
    }
    
    video_subject = None
    overlay_result = None  # Track overlay processing result
    
    try:
        # Step 1: Generate video subject
        print(f"\n[Pipeline] Step 1: Generating video subject (language={language})")
        last_voice = get_last_used_voice(language)
        voice_name = get_random_voice(last_voice, language)
        store_last_used_voice(voice_name)
        
        if campaign_input:
            video_subject = campaign_input.get("topic")
            if not video_subject:
                raise Exception("Campaign input did not provide a topic/title")
            print(f"[Pipeline] Using campaign input: {campaign_input.get('metadata', {}).get('source', args.campaign)}")
        else:
            video_subject = generate_video_subject(openai_api_key, language)
            if not video_subject:
                raise Exception("Failed to generate video subject - no topic returned")
        
        print(f"[Pipeline] Video subject: {video_subject}")
        
        # Step 2: Process subject and generate video
        print(f"\n[Pipeline] Step 2: Processing subject and generating video")
        if campaign_input and campaign_input.get("script"):
            video_script = campaign_input["script"]
            video_terms = tags_from_campaign(campaign_input, None)
            tags = video_terms
            print("[Pipeline] Using campaign-provided script/metadata")
        else:
            video_script, video_terms, tags = process_video_subject(video_subject, language)
            if campaign_input:
                tags = tags_from_campaign(campaign_input, tags)
                video_terms = tags
        upload_description = build_upload_description(video_subject, video_script, campaign_input.get("metadata", {}) if campaign_input else {})
        video_urls = generate_video_and_get_urls(video_subject, video_script, video_terms, voice_name, language)        
        if not video_urls:
            raise Exception("Failed to generate video - no URLs returned")
        
        original_video_url, converted_video_url = video_urls
        results["Video Generation"] = {
            "success": True,
            "details": f"Generated: {video_subject[:50]}..."
        }
        report_success("Video Generation", {"subject": video_subject, "url": original_video_url})
        
        # Step 3: Platform uploads
        if language == "en":
            # YouTube Upload
            skip_yt = os.getenv("SKIP_YT_UPLOAD", "false").lower() == "true"
            if skip_yt:
                results["YouTube Upload"]["skipped"] = True
                print("[Pipeline] YouTube upload skipped (SKIP_YT_UPLOAD=true)")
            else:
                print(f"\n[Pipeline] Step 3a: Uploading to YouTube")
                try:
                    print(f"[YouTube] Downloading video: {original_video_url}")
                    original_video_path = video_api_call.download_video(
                        original_video_url, video_subject, save_path="downloaded_videos"
                    )
                    
                    if not original_video_path:
                        raise Exception("Failed to download video for YouTube")

                    # Add controlled, self-generated BGM after generation.
                    # The upstream video API random BGM pool triggered YouTube Content ID claims.
                    if os.getenv("SAFE_BGM_ENABLED", "false").lower() == "true":
                        if SAFE_BGM_AVAILABLE:
                            try:
                                original_video_path = add_safe_background_music(original_video_path)
                                results["Safe BGM"] = {"success": True}
                            except Exception as bgm_error:
                                results["Safe BGM"] = {"success": False, "error": str(bgm_error)}
                                if os.getenv("SAFE_BGM_REQUIRED", "false").lower() == "true":
                                    raise Exception(f"Safe BGM mix failed: {bgm_error}")
                                print(f"[SafeBGM] Failed, continuing without BGM: {bgm_error}")
                        elif os.getenv("SAFE_BGM_REQUIRED", "false").lower() == "true":
                            raise Exception("Safe BGM is enabled but safe_background_music.py is unavailable")
                    else:
                        results["Safe BGM"] = {"skipped": True}
                    
                    # Run compliance check before upload
                    if args.skip_compliance:
                        results["Compliance Check"]["skipped"] = True
                        print("[Pipeline] Compliance check skipped (--skip-compliance)")
                    else:
                        compliance_result = run_compliance_check(
                            video_path=original_video_path,
                            title=video_subject,
                            description=upload_description,
                            source_url=original_video_url,
                            tags=tags
                        )
                        
                        if not compliance_result.passed:
                            results["Compliance Check"] = {
                                "success": False,
                                "error": "; ".join(compliance_result.issues)
                            }
                            # In strict mode, abort upload
                            if os.getenv("COMPLIANCE_ABORT_ON_FAIL", "false").lower() == "true":
                                raise Exception(f"Compliance check failed: {compliance_result.issues}")
                            print("[Compliance] Continuing despite failures (COMPLIANCE_ABORT_ON_FAIL=false)")
                        else:
                            results["Compliance Check"] = {"success": True}
                    
                    # Apply CTA overlay if configured and available
                    if CTA_OVERLAY_AVAILABLE and campaign_input:
                        campaign_metadata = campaign_input.get("metadata", {})
                        campaign_name = args.campaign
                        
                        print(f"[Pipeline] Checking for CTA overlay (campaign={campaign_name})")
                        overlay_result = process_video_with_overlay(
                            original_video_path,
                            campaign_metadata,
                            campaign_name=campaign_name,
                            video_subject=video_subject
                        )
                        
                        if overlay_result.get("overlay_applied"):
                            print(f"[Pipeline] CTA overlay applied successfully")
                            original_video_path = overlay_result["processed_path"]
                            results["CTA Overlay"] = {"success": True}
                        else:
                            print(f"[Pipeline] No CTA overlay configured for this campaign")
                    
                    youtube = authenticate_youtube()
                    upload_response = upload_video(youtube, original_video_path, video_subject, upload_description, tags)
                    
                    if upload_response:
                        video_id = upload_response["id"]
                        privacy = os.getenv("YOUTUBE_DEFAULT_PRIVACY", "private")
                        results["YouTube Upload"] = {
                            "success": True,
                            "details": f"Video ID: {video_id} (privacy: {privacy})"
                        }
                        send_notification_email(video_id, privacy)
                        report_success("YouTube Upload", {"video_id": video_id, "privacy": privacy})
                        
                        # Log instructions for manual publish if uploaded as private
                        if privacy == "private":
                            print(f"\n[YouTube] Video uploaded as PRIVATE for safety review.")
                            
                            # Check if auto-publish is enabled
                            auto_publish_enabled = os.getenv("YOUTUBE_AUTO_PUBLISH_AFTER_CHECK", "false").lower() == "true"
                            
                            if auto_publish_enabled and AUTO_PUBLISH_AVAILABLE:
                                print(f"[YouTube] Auto-publish enabled - checking processing status...")
                                results["Auto-Publish Check"] = {"success": False}
                                try:
                                    checker = AutoPublishChecker(youtube_service=youtube)
                                    auto_result = checker.check_and_publish(video_id)
                                    
                                    if auto_result.published:
                                        results["Auto-Publish Check"] = {
                                            "success": True,
                                            "details": f"Published as {auto_result.new_privacy}"
                                        }
                                        report_success("Auto-Publish", {
                                            "video_id": video_id,
                                            "new_privacy": auto_result.new_privacy
                                        })
                                    else:
                                        results["Auto-Publish Check"] = {
                                            "success": False,
                                            "details": f"Kept private: {auto_result.reason}"
                                        }
                                        print(f"[YouTube] Video kept private: {auto_result.reason}")
                                        print(f"[YouTube] To manually publish after review, run:")
                                        print(f"    python publish_video.py {video_id}")
                                except Exception as ap_error:
                                    results["Auto-Publish Check"]["error"] = str(ap_error)
                                    report_error("Auto-Publish Check", ap_error, {"video_id": video_id})
                                    print(f"[YouTube] Auto-publish check failed: {ap_error}")
                                    print(f"[YouTube] To manually publish after review, run:")
                                    print(f"    python publish_video.py {video_id}")
                            else:
                                # Manual publish instructions
                                print(f"[YouTube] To publish after review, run:")
                                print(f"    python main.py --publish-after-check --video-id {video_id}")
                                print(f"[YouTube] Or set YOUTUBE_DEFAULT_PRIVACY=public in .env")
                                if not AUTO_PUBLISH_AVAILABLE:
                                    print(f"[YouTube] Note: auto_publish_checker module not available")
                    else:
                        raise Exception("Upload returned no response")
                        
                except Exception as e:
                    results["YouTube Upload"]["error"] = str(e)
                    report_error("YouTube Upload", e, {"video_subject": video_subject})
            
            # Instagram Upload
            skip_ig = os.getenv("SKIP_IG_UPLOAD", "false").lower() == "true"
            if skip_ig:
                results["Instagram Upload"]["skipped"] = True
                print("[Pipeline] Instagram upload skipped (SKIP_IG_UPLOAD=true)")
            else:
                print(f"\n[Pipeline] Step 3b: Uploading to Instagram")
                try:
                    # Determine which URL to use for Instagram
                    # Priority: 1) Public URL from overlay, 2) converted_video_url, 3) original_video_url
                    if overlay_result and overlay_result.get("public_url"):
                        upload_url = overlay_result["public_url"]
                        print(f"[Instagram] Using CTA overlay public URL: {upload_url}")
                    else:
                        upload_url = converted_video_url if converted_video_url else original_video_url
                        print(f"[Instagram] Using video URL: {upload_url}")
                    
                    success, result = publish_video_to_instagram(ig_user_id, upload_url, ig_access_token, caption=upload_description)
                    
                    if success:
                        results["Instagram Upload"] = {
                            "success": True,
                            "details": f"Media ID: {result.get('media_id')}"
                        }
                        send_instagram_notification_email()
                        report_success("Instagram Upload", result)
                    else:
                        error_msg = result.get("error", "Unknown error")
                        is_token_error = result.get("is_token_error", False)
                        
                        results["Instagram Upload"]["error"] = error_msg
                        results["Instagram Upload"]["is_token_error"] = is_token_error
                        
                        # Report with specific context for token errors
                        report_error(
                            "Instagram Upload", 
                            Exception(error_msg),
                            {
                                "video_subject": video_subject,
                                "video_url": upload_url,
                                "is_token_error": is_token_error
                            }
                        )
                        
                except Exception as e:
                    results["Instagram Upload"]["error"] = str(e)
                    report_error("Instagram Upload", e, {"video_subject": video_subject})
                    
        elif language == "zh":
            # Chinese platforms
            print(f"\n[Pipeline] Step 3: Uploading to Chinese platforms")
            try:
                video_download_path = get_download_path()
                original_video_path = video_api_call.download_video(
                    original_video_url, video_subject, save_path=video_download_path
                )
                
                if not original_video_path:
                    raise Exception("Failed to download video for Chinese platforms")
                
                original_video_path = linux_to_windows_path(os.path.abspath(original_video_path))
                print(f"[Chinese] Video path: {original_video_path}")
                
                asyncio.run(upload_to_chinese_platforms(
                    original_video_path, video_subject, upload_description, tags, results
                ))
                
            except Exception as e:
                results["Chinese Platforms"] = {"success": False, "error": str(e)}
                report_error("Chinese Platforms", e, {"video_subject": video_subject})
        
    except Exception as e:
        results["Video Generation"]["error"] = str(e)
        report_error("Video Generation", e, {"video_subject": video_subject})
    
    # Print summary
    summary = create_run_summary(results)
    print(summary)
    
    # Determine exit code
    critical_failures = [
        r for r in results.values() 
        if not r.get("success") and not r.get("skipped") and r.get("error")
    ]
    
    if critical_failures:
        print(f"\n[Pipeline] Completed with {len(critical_failures)} failure(s)")
        return 1
    
    print("\n[Pipeline] Completed successfully")
    return 0


async def upload_to_chinese_platforms(video_path, video_subject, video_script, tags, results):
    """Upload video to Chinese platforms."""
    platforms = ["xhs"]
    
    for platform in platforms:
        platform_key = f"Chinese/{platform.upper()}"
        results[platform_key] = {"success": False}
        
        try:
            headless = os.getenv("HEADLESS", "true").lower() == "true"
            use_mcp = platform == "xhs" and os.getenv("XHS_MCP_ENABLED", "false").lower() == "true"
            
            upload_success = await chinese_uploader_main(
                platform_name=platform,
                video_url="",
                video_path=video_path,
                video_name=video_subject,
                cover_path=None,
                description=video_script,
                topics=tags,
                headless=headless,
                use_mcp=use_mcp
            )
            
            if upload_success:
                results[platform_key] = {"success": True, "details": "Upload completed"}
                send_chinese_platform_notification_email(platform, video_subject)
                report_success(f"Chinese/{platform}", {"video": video_subject})
            else:
                raise Exception(f"Upload to {platform} returned failure")
                
        except Exception as e:
            results[platform_key]["error"] = str(e)
            report_error(f"Chinese/{platform}", e, {"video_subject": video_subject})


def send_chinese_platform_notification_email(platform_name, video_name):
    subject = f"Video Uploaded to {platform_name.capitalize()}"
    body = f"Your video '{video_name}' has been uploaded to {platform_name.capitalize()}!"
    send_email(subject, body, ["jack_hui@msn.com"])


def send_notification_email(video_id, privacy="private"):
    subject = f"YouTube Video Uploaded ({privacy.upper()})"
    body = f"""Your video has been uploaded to YouTube!

Video ID: {video_id}
URL: https://youtube.com/watch?v={video_id}
Privacy: {privacy.upper()}
"""
    if privacy == "private":
        body += f"""
The video was uploaded as PRIVATE for safety review.
To publish it, run:
    python main.py --publish-after-check --video-id {video_id}

Or set YOUTUBE_DEFAULT_PRIVACY=public in your .env file for future uploads.
"""
    send_email(subject, body, ["jack_hui@msn.com"])


def send_instagram_notification_email():
    subject = "Instagram Reel Uploaded Successfully"
    body = "Your video has been uploaded to Instagram Reels!"
    send_email(subject, body, ["jack_hui@msn.com"])


if __name__ == "__main__":
    sys.exit(main())
