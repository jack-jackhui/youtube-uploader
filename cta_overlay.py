"""
CTA Overlay Module - Generic Text/CTA Overlay for Video Campaigns

A reusable module for burning text overlays (CTAs, branding, URLs) into videos.
Supports configurable text, positioning, timing, and styling.

Usage:
    # From campaign backlog metadata:
    "cta_overlay": {
        "enabled": true,
        "text": "Try WinningCV free",
        "url": "winning-cv.jackhui.com.au",
        "position": "lower_third",     # lower_third | center | top
        "style": "box",                 # box | shadow | minimal
        "start_seconds_from_end": 8,    # when lower-third appears
        "end_card_seconds": 2,          # duration of final centered overlay
        "font_size": 42,                # optional custom size
        "font_color": "white"           # optional color
    }
    
    # Programmatic usage:
    from cta_overlay import apply_cta_overlay, OverlayConfig
    
    config = OverlayConfig.from_dict(backlog_entry.get("cta_overlay", {}))
    if config.enabled:
        result = apply_cta_overlay(video_path, config)
"""

import os
import subprocess
import shutil
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class OverlayConfig:
    """Configuration for CTA/text overlay on videos."""
    
    enabled: bool = False
    text: str = ""
    url: str = ""
    position: str = "lower_third"  # lower_third | center | top
    style: str = "box"  # box | shadow | minimal
    start_seconds_from_end: float = 8.0  # when lower-third begins
    end_card_seconds: float = 2.0  # duration of final centered card
    font_size: Optional[int] = None  # auto-calculated if None
    font_color: str = "white"
    background_color: str = "black"
    background_opacity: float = 0.6
    is_vertical: bool = True  # 9:16 vs 16:9
    
    # Output configuration
    output_suffix: str = "_with_cta"
    replace_original: bool = True
    
    # Public serving (for Instagram)
    publish_public: bool = False
    public_video_dir: str = "/var/www/jackhui.com.au/build/videos"
    public_base_url: str = "https://jackhui.com.au/videos"
    
    @property
    def display_text(self) -> str:
        """Formatted display text combining text and URL."""
        parts = []
        if self.text:
            parts.append(self.text)
        if self.url:
            # Clean URL for display
            clean_url = self.url.replace("https://", "").replace("http://", "")
            if self.text:
                parts.append(f": {clean_url}")
            else:
                parts.append(clean_url)
        return "".join(parts) or "Visit our website"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None) -> "OverlayConfig":
        """
        Create config from dictionary (e.g., backlog metadata).
        
        Args:
            data: Config dictionary from backlog entry
            defaults: Optional campaign-level defaults to merge
        """
        if defaults:
            merged = {**defaults, **data}
        else:
            merged = data
            
        return cls(
            enabled=merged.get("enabled", False),
            text=merged.get("text", ""),
            url=merged.get("url", ""),
            position=merged.get("position", "lower_third"),
            style=merged.get("style", "box"),
            start_seconds_from_end=float(merged.get("start_seconds_from_end", 8.0)),
            end_card_seconds=float(merged.get("end_card_seconds", 2.0)),
            font_size=merged.get("font_size"),
            font_color=merged.get("font_color", "white"),
            background_color=merged.get("background_color", "black"),
            background_opacity=float(merged.get("background_opacity", 0.6)),
            is_vertical=merged.get("is_vertical", True),
            output_suffix=merged.get("output_suffix", "_with_cta"),
            replace_original=merged.get("replace_original", True),
            publish_public=merged.get("publish_public", False),
            public_video_dir=merged.get("public_video_dir", "/var/www/jackhui.com.au/build/videos"),
            public_base_url=merged.get("public_base_url", "https://jackhui.com.au/videos"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Export config as dictionary."""
        return {
            "enabled": self.enabled,
            "text": self.text,
            "url": self.url,
            "position": self.position,
            "style": self.style,
            "start_seconds_from_end": self.start_seconds_from_end,
            "end_card_seconds": self.end_card_seconds,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "background_color": self.background_color,
            "background_opacity": self.background_opacity,
            "is_vertical": self.is_vertical,
        }


# ==============================================================================
# Preset Configurations
# ==============================================================================

PRESETS: Dict[str, Dict[str, Any]] = {
    "winningcv": {
        "enabled": True,
        "text": "Try WinningCV free",
        "url": "winning-cv.jackhui.com.au",
        "position": "lower_third",
        "style": "box",
        "start_seconds_from_end": 8,
        "end_card_seconds": 2,
        "publish_public": True,
    },
    "selectprep": {
        "enabled": True,
        "text": "Ace your interview",
        "url": "selectprep.com.au",
        "position": "lower_third",
        "style": "box",
        "start_seconds_from_end": 8,
        "end_card_seconds": 2,
        "publish_public": True,
    },
    "minimal": {
        "enabled": True,
        "text": "",
        "url": "",
        "position": "lower_third",
        "style": "minimal",
        "start_seconds_from_end": 5,
        "end_card_seconds": 0,
    },
}


def get_preset(name: str) -> OverlayConfig:
    """Get a preset configuration by name."""
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(PRESETS.keys())}")
    return OverlayConfig.from_dict(PRESETS[name])


# ==============================================================================
# Video Processing
# ==============================================================================

def get_video_duration(video_path: str) -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.error(f"Failed to get video duration: {e}")
        return None


def get_video_dimensions(video_path: str) -> Optional[tuple]:
    """Get video dimensions (width, height) using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=p=0',
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parts = result.stdout.strip().split(',')
        return int(parts[0]), int(parts[1])
    except (subprocess.CalledProcessError, ValueError, IndexError) as e:
        logger.error(f"Failed to get video dimensions: {e}")
        return None


def _escape_ffmpeg_text(text: str) -> str:
    """Escape special characters for ffmpeg drawtext filter."""
    # Escape backslash first, then other special chars
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    return text


def _build_filter_chain(config: OverlayConfig, duration: float) -> str:
    """Build ffmpeg filter chain for overlay effects."""
    
    display_text = _escape_ffmpeg_text(config.display_text)
    
    # Calculate timing
    lower_third_start = max(0, duration - config.start_seconds_from_end)
    end_card_start = max(0, duration - config.end_card_seconds) if config.end_card_seconds > 0 else duration
    
    # Font configuration
    font_file = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    
    # Calculate font sizes based on video orientation
    if config.is_vertical:
        font_size_lower = config.font_size or 42
        font_size_end = int(font_size_lower * 1.3)
        lower_y = "h-h*0.12"
    else:
        font_size_lower = config.font_size or 36
        font_size_end = int(font_size_lower * 1.3)
        lower_y = "h-h*0.15"
    
    # Position expressions
    position_map = {
        "lower_third": lower_y,
        "center": "(h-text_h)/2",
        "top": "h*0.08",
    }
    y_position = position_map.get(config.position, lower_y)
    
    # Build style-specific filters
    filters = []
    
    # Style variations
    if config.style == "box":
        box_params = f":box=1:boxcolor={config.background_color}@{config.background_opacity}:boxborderw=10"
    elif config.style == "shadow":
        box_params = f":shadowcolor=black@0.8:shadowx=2:shadowy=2"
    else:  # minimal
        box_params = ""
    
    # Lower-third overlay (if we have time for it before end card)
    if lower_third_start < end_card_start:
        filters.append(
            f"drawtext=text='{display_text}'"
            f":fontsize={font_size_lower}"
            f":fontcolor={config.font_color}"
            f":fontfile={font_file}"
            f":x=(w-text_w)/2"
            f":y={y_position}"
            f"{box_params}"
            f":enable='between(t,{lower_third_start:.2f},{end_card_start:.2f})'"
        )
    
    # End card (if configured)
    if config.end_card_seconds > 0:
        # Dim overlay
        filters.append(
            f"drawbox=x=0:y=0:w=iw:h=ih:color={config.background_color}@0.5"
            f":enable='gte(t,{end_card_start:.2f})'"
        )
        # Centered text
        filters.append(
            f"drawtext=text='{display_text}'"
            f":fontsize={font_size_end}"
            f":fontcolor={config.font_color}"
            f":fontfile={font_file}"
            f":x=(w-text_w)/2"
            f":y=(h-text_h)/2"
            f":enable='gte(t,{end_card_start:.2f})'"
        )
    
    return ",".join(filters)


def apply_cta_overlay(
    input_path: str,
    config: OverlayConfig,
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    Apply CTA/text overlay to a video using ffmpeg.
    
    Args:
        input_path: Path to input video
        config: OverlayConfig with overlay settings
        output_path: Optional custom output path
        
    Returns:
        str: Path to processed video, or None on failure
    """
    if not config.enabled:
        logger.info("[CTA Overlay] Overlay disabled, returning original path")
        return input_path
        
    if not os.path.exists(input_path):
        logger.error(f"[CTA Overlay] Input video not found: {input_path}")
        return None
    
    # Get video properties
    duration = get_video_duration(input_path)
    if duration is None:
        logger.error("[CTA Overlay] Could not determine video duration")
        return None
    
    dimensions = get_video_dimensions(input_path)
    if dimensions:
        width, height = dimensions
        config.is_vertical = height > width
        logger.info(f"[CTA Overlay] Detected {'vertical' if config.is_vertical else 'horizontal'} video: {width}x{height}")
    
    # Determine output path
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}{config.output_suffix}{ext}"
    
    # Build filter chain
    filter_chain = _build_filter_chain(config, duration)
    
    if not filter_chain:
        logger.warning("[CTA Overlay] No filters to apply")
        return input_path
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', filter_chain,
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'copy',
        output_path
    ]
    
    logger.info(f"[CTA Overlay] Processing: {input_path}")
    logger.info(f"[CTA Overlay] Text: {config.display_text}")
    logger.info(f"[CTA Overlay] Style: {config.style}, Position: {config.position}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            # Replace original if configured
            if config.replace_original and output_path != input_path:
                shutil.move(output_path, input_path)
                logger.info(f"[CTA Overlay] Successfully processed (replaced original): {input_path}")
                return input_path
            else:
                logger.info(f"[CTA Overlay] Successfully processed: {output_path}")
                return output_path
        else:
            logger.error(f"[CTA Overlay] Output file missing or empty: {output_path}")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"[CTA Overlay] ffmpeg failed: {e.stderr}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None


# ==============================================================================
# Public Video Serving (for Instagram)
# ==============================================================================

def ensure_public_dir(config: OverlayConfig) -> str:
    """Ensure the public video directory exists."""
    if not os.path.exists(config.public_video_dir):
        os.makedirs(config.public_video_dir, mode=0o755, exist_ok=True)
    return config.public_video_dir


def publish_video_for_instagram(
    local_video_path: str,
    config: OverlayConfig,
    video_subject: Optional[str] = None
) -> tuple:
    """
    Copy a processed video to the public web directory for Instagram access.
    
    Args:
        local_video_path: Path to the local video file
        config: OverlayConfig with public serving settings
        video_subject: Optional subject for filename
        
    Returns:
        tuple: (public_url, public_path) or (None, None) on failure
    """
    if not config.publish_public:
        logger.info("[CTA Overlay] Public publishing disabled")
        return None, None
        
    if not os.path.exists(local_video_path):
        logger.error(f"[CTA Overlay] Video not found: {local_video_path}")
        return None, None
        
    ensure_public_dir(config)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if video_subject:
        subject_hash = hashlib.md5(video_subject.encode()).hexdigest()[:8]
        filename = f"campaign_{timestamp}_{subject_hash}.mp4"
    else:
        filename = f"campaign_{timestamp}.mp4"
    
    public_path = os.path.join(config.public_video_dir, filename)
    
    try:
        shutil.copy2(local_video_path, public_path)
        os.chmod(public_path, 0o644)
        
        public_url = f"{config.public_base_url}/{filename}"
        logger.info(f"[CTA Overlay] Published for Instagram: {public_url}")
        return public_url, public_path
        
    except Exception as e:
        logger.error(f"[CTA Overlay] Failed to publish video: {e}")
        return None, None


def cleanup_old_public_videos(config: OverlayConfig, max_age_hours: int = 48) -> int:
    """
    Remove old public videos to save disk space.
    
    Returns:
        int: Number of files cleaned up
    """
    if not os.path.exists(config.public_video_dir):
        return 0
        
    cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
    cleaned = 0
    
    for filename in os.listdir(config.public_video_dir):
        if not filename.startswith("campaign_"):
            continue
        filepath = os.path.join(config.public_video_dir, filename)
        try:
            if os.path.getmtime(filepath) < cutoff_time:
                os.remove(filepath)
                logger.info(f"[CTA Overlay] Cleaned up old video: {filename}")
                cleaned += 1
        except Exception as e:
            logger.warning(f"[CTA Overlay] Failed to cleanup {filename}: {e}")
    
    return cleaned


# ==============================================================================
# Pipeline Integration Helper
# ==============================================================================

def process_video_with_overlay(
    video_path: str,
    campaign_metadata: Dict[str, Any],
    campaign_name: str = "default",
    video_subject: Optional[str] = None
) -> Dict[str, Any]:
    """
    High-level helper for pipeline integration.
    
    Checks if overlay is configured in metadata, applies it if enabled,
    and optionally publishes to public URL for Instagram.
    
    Args:
        video_path: Path to downloaded video
        campaign_metadata: Full metadata dict from backlog entry
        campaign_name: Campaign name for preset fallback
        video_subject: Video subject/title for filename generation
        
    Returns:
        dict: {
            "processed_path": str,  # Path to processed video
            "overlay_applied": bool,
            "public_url": str or None,  # URL for Instagram if published
            "public_path": str or None,
        }
    """
    result = {
        "processed_path": video_path,
        "overlay_applied": False,
        "public_url": None,
        "public_path": None,
    }
    
    # Extract overlay config from metadata
    overlay_data = campaign_metadata.get("cta_overlay", {})
    
    # If no explicit config but campaign has a preset, use it
    if not overlay_data and campaign_name.lower() in PRESETS:
        logger.info(f"[CTA Overlay] Using preset for campaign: {campaign_name}")
        overlay_data = PRESETS[campaign_name.lower()]
    
    # Build config
    config = OverlayConfig.from_dict(overlay_data)
    
    if not config.enabled:
        logger.info("[CTA Overlay] Overlay not enabled for this video")
        return result
    
    # Apply overlay
    processed_path = apply_cta_overlay(video_path, config)
    
    if processed_path:
        result["processed_path"] = processed_path
        result["overlay_applied"] = True
        
        # Publish for Instagram if configured
        if config.publish_public:
            public_url, public_path = publish_video_for_instagram(
                processed_path, config, video_subject
            )
            result["public_url"] = public_url
            result["public_path"] = public_path
    
    return result


# ==============================================================================
# Testing
# ==============================================================================

def test_overlay_with_config(config: OverlayConfig, test_duration: int = 10) -> bool:
    """
    Test overlay with a specific configuration on a synthetic video.
    
    Args:
        config: OverlayConfig to test
        test_duration: Duration of synthetic test video in seconds
        
    Returns:
        bool: True if test passed
    """
    import tempfile
    
    test_dir = tempfile.mkdtemp()
    test_input = os.path.join(test_dir, "test_input.mp4")
    test_output = os.path.join(test_dir, "test_output.mp4")
    
    # Determine dimensions based on orientation
    if config.is_vertical:
        dimensions = "1080x1920"
    else:
        dimensions = "1920x1080"
    
    # Generate synthetic video
    create_cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi', '-i', f'color=c=darkblue:s={dimensions}:d={test_duration}:r=30',
        '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
        '-t', str(test_duration),
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-c:a', 'aac', '-shortest',
        test_input
    ]
    
    logger.info(f"[Test] Creating synthetic {dimensions} video ({test_duration}s)...")
    result = subprocess.run(create_cmd, capture_output=True, text=True)
    
    if result.returncode != 0 or not os.path.exists(test_input):
        logger.error(f"[Test] Failed to create test video: {result.stderr}")
        shutil.rmtree(test_dir)
        return False
    
    # Don't replace original during test
    test_config = OverlayConfig.from_dict(config.to_dict())
    test_config.replace_original = False
    
    # Apply overlay
    result_path = apply_cta_overlay(test_input, test_config, output_path=test_output)
    
    success = result_path is not None and os.path.exists(result_path)
    
    if success:
        size = os.path.getsize(result_path)
        logger.info(f"[Test] SUCCESS - Output: {result_path} ({size} bytes)")
    else:
        logger.error("[Test] FAILED - Overlay application failed")
    
    shutil.rmtree(test_dir)
    return success


def run_all_tests() -> Dict[str, bool]:
    """Run tests for all presets."""
    results = {}
    
    for preset_name in PRESETS:
        logger.info(f"\n[Test] Testing preset: {preset_name}")
        config = get_preset(preset_name)
        results[preset_name] = test_overlay_with_config(config, test_duration=10)
    
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 60)
    print("CTA Overlay Module - Test Suite")
    print("=" * 60)
    
    results = run_all_tests()
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    print(f"\nOverall: {'✅ All tests passed' if all_passed else '❌ Some tests failed'}")
