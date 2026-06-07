# CTA Overlay Module

A reusable module for burning text overlays (CTAs, branding, URLs) into videos.

## Overview

The CTA overlay module (`cta_overlay.py`) provides:
- Configurable text overlays with timing control
- Lower-third and end-card display modes
- Multiple styling options (box, shadow, minimal)
- Automatic public URL generation for Instagram
- Preset configurations for common campaigns

## Configuration

### Backlog-Level Configuration (Recommended)

Add `cta_overlay` to your campaign backlog JSON to apply overlay to all videos:

```json
{
  "campaign": "WinningCV Launch",
  "platforms": ["youtube", "instagram"],
  "start_date": "2026-05-06",
  "cta_overlay": {
    "enabled": true,
    "text": "Try WinningCV free",
    "url": "winning-cv.jackhui.com.au",
    "position": "lower_third",
    "style": "box",
    "start_seconds_from_end": 8,
    "end_card_seconds": 2,
    "publish_public": true
  },
  "videos": [...]
}
```

### Per-Video Override

Override campaign-level settings for specific videos:

```json
{
  "day": 5,
  "topic": "Special Promo Video",
  "cta_overlay": {
    "enabled": true,
    "text": "50% OFF This Week",
    "url": "winning-cv.jackhui.com.au/promo",
    "end_card_seconds": 3
  }
}
```

### Disable Overlay for Specific Videos

```json
{
  "day": 10,
  "topic": "Behind the Scenes",
  "cta_overlay": {
    "enabled": false
  }
}
```

## Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable/disable overlay |
| `text` | string | `""` | Main CTA text (e.g., "Try WinningCV free", "Ace selective entry exams") |
| `url` | string | `""` | URL to display (e.g., "winning-cv.jackhui.com.au") |
| `position` | string | `"lower_third"` | Where overlay appears: `lower_third`, `center`, `top` |
| `style` | string | `"box"` | Visual style: `box` (dark background), `shadow`, `minimal` |
| `start_seconds_from_end` | number | `8` | When lower-third starts (seconds before video end) |
| `end_card_seconds` | number | `2` | Duration of centered end card (0 to disable) |
| `font_size` | number | auto | Custom font size (auto-calculated based on video orientation) |
| `font_color` | string | `"white"` | Text color |
| `background_color` | string | `"black"` | Background color for box style |
| `background_opacity` | number | `0.6` | Background transparency (0-1) |
| `publish_public` | boolean | `false` | Copy processed video to public URL for Instagram |

## Presets

The module includes built-in presets for common campaigns:

### WinningCV (default for `--campaign winningcv`)
```json
{
  "enabled": true,
  "text": "Try WinningCV free",
  "url": "winning-cv.jackhui.com.au",
  "position": "lower_third",
  "style": "box",
  "start_seconds_from_end": 8,
  "end_card_seconds": 2,
  "publish_public": true
}
```

### SelectPrep (default for `--campaign selectprep`)
```json
{
  "enabled": true,
  "text": "Ace selective entry exams",
  "url": "selectprep.com.au",
  "position": "lower_third",
  "style": "box",
  "start_seconds_from_end": 8,
  "end_card_seconds": 2,
  "publish_public": true
}
```

### Minimal
```json
{
  "enabled": true,
  "text": "",
  "url": "",
  "position": "lower_third",
  "style": "minimal",
  "start_seconds_from_end": 5,
  "end_card_seconds": 0
}
```

## How It Works

1. **Video Downloaded**: Pipeline downloads video from AI video API
2. **Overlay Check**: If `cta_overlay.enabled` in metadata, apply overlay
3. **ffmpeg Processing**: Burns in text using `drawtext` filter
4. **YouTube Upload**: Uploads processed video to YouTube
5. **Instagram**: If `publish_public=true`, copies to web server and uses public URL

### Overlay Timeline (15-second video example)

```
0s        7s        13s       15s
|---------|---------|---------|
          |lower-3rd|end-card |
          ↑         ↑
          8s before 2s before
          end       end
```

## Usage Examples

### Command Line (with preset)
```bash
# Uses winningcv preset automatically
python main.py --backlog winning-cv-video-backlog.json --day 1 --campaign winningcv

# Uses selectprep preset automatically
python main.py --backlog selectprep-video-backlog.json --day 1 --campaign selectprep
```

### Programmatic Usage
```python
from cta_overlay import process_video_with_overlay, OverlayConfig, get_preset

# From backlog metadata
result = process_video_with_overlay(
    video_path="/path/to/video.mp4",
    campaign_metadata={"cta_overlay": {"enabled": True, "text": "Visit us"}},
    campaign_name="custom",
    video_subject="My Video"
)

# Using preset
config = get_preset("winningcv")
from cta_overlay import apply_cta_overlay
apply_cta_overlay("/path/to/video.mp4", config)
```

## Legacy Compatibility

- **No overlay config**: Normal pipeline, no overlay applied
- **No cta_overlay module**: Graceful fallback, logs warning, continues without overlay
- **enabled: false**: Skips overlay, uses original video

## Testing

Run the built-in test suite:
```bash
cd /home/ubuntu/youtube-uploader
source venv/bin/activate
python cta_overlay.py
```

## Requirements

- ffmpeg (installed: `sudo apt install ffmpeg`)
- DejaVu fonts (installed: `/usr/share/fonts/truetype/dejavu/`)
- Public video directory: `/var/www/jackhui.com.au/build/videos/`
