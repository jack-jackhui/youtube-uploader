# compliance_gate.py
"""
Pre-upload compliance gate for copyright safety.
Checks videos before uploading to detect potential copyright issues.
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Blocklist of risky sources (known copyright-risk domains)
BLOCKLIST_SOURCES = [
    # Video platforms (direct ripping)
    "youtube.com", "youtu.be",
    "vimeo.com",
    "dailymotion.com",
    "twitch.tv",
    "tiktok.com",
    "instagram.com/reel",
    "facebook.com/watch",
    
    # News/media sites with copyrighted content
    "cnn.com/videos",
    "bbc.com/news/av",
    "nbcnews.com/video",
    "reuters.com/video",
    
    # Music platforms
    "spotify.com",
    "soundcloud.com",
    "music.apple.com",
    "deezer.com",
]

# Keywords indicating potential copyright issues
RISKY_KEYWORDS = [
    # Music-related
    "official music video",
    "official video",
    "music video",
    "full album",
    "full song",
    "lyrics video",
    
    # Movie/TV related
    "full movie",
    "full episode",
    "movie clip",
    "tv show",
    "trailer official",
    
    # Sports
    "match highlights",
    "game highlights",
    "full game",
    "nba", "nfl", "mlb", "premier league",
]

# Safe source indicators
SAFE_SOURCE_PATTERNS = [
    r"pexels\.com",
    r"pixabay\.com", 
    r"unsplash\.com",
    r"freepik\.com",
    r"mixkit\.co",
    r"videvo\.net",
    r"coverr\.co",
    r"generated.*video",
    r"ai.*generated",
    r"ai-video-generator",
    r"moneyprinterturbo",
    r"nativevoices",
]


@dataclass
class ComplianceResult:
    """Result of a compliance check."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class ComplianceGate:
    """
    Pre-upload compliance gate that checks for potential copyright issues.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize compliance gate.
        
        Args:
            config: Optional configuration dict with:
                - blocklist_file: Path to custom blocklist file
                - strict_mode: If True, warnings become errors
                - require_source_manifest: If True, source metadata is required
        """
        self.config = config or {}
        self.strict_mode = self.config.get("strict_mode", False)
        self.require_source_manifest = self.config.get("require_source_manifest", False)
        self.blocklist = set(BLOCKLIST_SOURCES)
        
        # Load custom blocklist if provided
        blocklist_file = self.config.get("blocklist_file")
        if blocklist_file and os.path.exists(blocklist_file):
            self._load_custom_blocklist(blocklist_file)
    
    def _load_custom_blocklist(self, filepath: str) -> None:
        """Load additional blocked sources from a file."""
        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.blocklist.add(line.lower())
            logger.info(f"Loaded {len(self.blocklist)} blocked sources")
        except Exception as e:
            logger.warning(f"Failed to load blocklist file: {e}")
    
    def check_source_url(self, source_url: Optional[str]) -> Tuple[bool, List[str]]:
        """
        Check if source URL is from a blocked domain.
        
        Returns:
            Tuple of (is_safe, list of issues)
        """
        if not source_url:
            if self.require_source_manifest:
                return False, ["No source URL provided (source manifest required)"]
            return True, []
        
        issues = []
        source_lower = source_url.lower()
        
        # Check blocklist
        for blocked in self.blocklist:
            if blocked in source_lower:
                issues.append(f"Source URL contains blocked domain: {blocked}")
        
        # Check for safe source patterns
        is_safe_source = any(
            re.search(pattern, source_lower) 
            for pattern in SAFE_SOURCE_PATTERNS
        )
        
        if not is_safe_source and not issues:
            # Not explicitly blocked but not a known safe source
            issues.append(f"Source URL not from verified safe source: {source_url[:100]}")
        
        return len(issues) == 0, issues
    
    def check_title_description(
        self, 
        title: str, 
        description: str
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Check title and description for risky keywords.
        
        Returns:
            Tuple of (is_safe, issues, warnings)
        """
        issues = []
        warnings = []
        
        combined_text = f"{title} {description}".lower()
        
        for keyword in RISKY_KEYWORDS:
            if keyword in combined_text:
                warnings.append(f"Contains risky keyword: {keyword}")
        
        # Check for overly generic/template-like titles
        generic_patterns = [
            r"^video \d+$",
            r"^test video$",
            r"^untitled$",
        ]
        for pattern in generic_patterns:
            if re.match(pattern, title.lower()):
                warnings.append(f"Title appears generic/template-like: {title}")
        
        # In strict mode, warnings become issues
        if self.strict_mode and warnings:
            issues.extend(warnings)
            warnings = []
        
        return len(issues) == 0, issues, warnings
    
    def check_video_metadata(
        self,
        video_path: Optional[str] = None,
        source_manifest: Optional[Dict] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Check video metadata for compliance.
        
        Args:
            video_path: Path to video file
            source_manifest: Dict with source info like:
                - source_type: "ai_generated", "stock_footage", "original", etc.
                - license: License type
                - attribution: Required attribution
                
        Returns:
            Tuple of (is_safe, issues, warnings)
        """
        issues = []
        warnings = []
        
        if self.require_source_manifest:
            if not source_manifest:
                issues.append("Source manifest required but not provided")
            else:
                source_type = source_manifest.get("source_type", "")
                if source_type not in ["ai_generated", "stock_footage", "original", "creative_commons"]:
                    warnings.append(f"Unknown source type: {source_type}")
                
                if not source_manifest.get("license"):
                    warnings.append("No license information in source manifest")
        
        # Check video file exists
        if video_path and not os.path.exists(video_path):
            issues.append(f"Video file not found: {video_path}")
        
        if self.strict_mode and warnings:
            issues.extend(warnings)
            warnings = []
        
        return len(issues) == 0, issues, warnings
    
    def run_compliance_check(
        self,
        video_path: Optional[str] = None,
        title: str = "",
        description: str = "",
        source_url: Optional[str] = None,
        source_manifest: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ) -> ComplianceResult:
        """
        Run full compliance check before upload.
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            source_url: URL where video/content was sourced from
            source_manifest: Dict with source metadata
            tags: Video tags
            
        Returns:
            ComplianceResult with pass/fail status and details
        """
        all_issues = []
        all_warnings = []
        metadata = {
            "video_path": video_path,
            "title": title[:100] if title else None,
            "source_url": source_url[:200] if source_url else None,
            "has_source_manifest": source_manifest is not None,
            "checks_run": [],
        }
        
        # 1. Check source URL
        metadata["checks_run"].append("source_url")
        url_safe, url_issues = self.check_source_url(source_url)
        all_issues.extend(url_issues)
        
        # 2. Check title/description
        metadata["checks_run"].append("title_description")
        td_safe, td_issues, td_warnings = self.check_title_description(title, description)
        all_issues.extend(td_issues)
        all_warnings.extend(td_warnings)
        
        # 3. Check video metadata
        metadata["checks_run"].append("video_metadata")
        vm_safe, vm_issues, vm_warnings = self.check_video_metadata(video_path, source_manifest)
        all_issues.extend(vm_issues)
        all_warnings.extend(vm_warnings)
        
        # 4. Check tags for risky content
        if tags:
            metadata["checks_run"].append("tags")
            tags_lower = " ".join(tags).lower()
            for keyword in RISKY_KEYWORDS:
                if keyword in tags_lower:
                    all_warnings.append(f"Tag contains risky keyword: {keyword}")
        
        passed = len(all_issues) == 0
        
        return ComplianceResult(
            passed=passed,
            issues=all_issues,
            warnings=all_warnings,
            metadata=metadata
        )


def load_compliance_config() -> Dict:
    """Load compliance configuration from environment or config file."""
    config = {
        "strict_mode": os.getenv("COMPLIANCE_STRICT_MODE", "false").lower() == "true",
        "require_source_manifest": os.getenv("COMPLIANCE_REQUIRE_MANIFEST", "false").lower() == "true",
        "blocklist_file": os.getenv("COMPLIANCE_BLOCKLIST_FILE"),
    }
    return config


# Convenience function for simple checks
def check_before_upload(
    video_path: Optional[str] = None,
    title: str = "",
    description: str = "",
    source_url: Optional[str] = None,
    tags: Optional[List[str]] = None,
    strict: bool = False
) -> ComplianceResult:
    """
    Quick compliance check before upload.
    
    Example:
        result = check_before_upload(
            video_path="/path/to/video.mp4",
            title="My AI Generated Video",
            description="A video about tech",
            source_url="https://ai-video-generator.com/video/123"
        )
        if not result.passed:
            print(f"Compliance failed: {result.issues}")
    """
    config = load_compliance_config()
    config["strict_mode"] = strict or config.get("strict_mode", False)
    
    gate = ComplianceGate(config)
    return gate.run_compliance_check(
        video_path=video_path,
        title=title,
        description=description,
        source_url=source_url,
        tags=tags
    )


if __name__ == "__main__":
    # Test the compliance gate
    print("Testing compliance gate...")
    
    # Test 1: Clean video
    result = check_before_upload(
        title="Is AI about to replace your favorite app?",
        description="Exploring the latest trends in AI technology",
        source_url="https://ai-video-generator.com/video/123"
    )
    print(f"Test 1 (clean): passed={result.passed}, issues={result.issues}, warnings={result.warnings}")
    
    # Test 2: Risky source
    result = check_before_upload(
        title="Amazing Tech News",
        description="Latest tech updates",
        source_url="https://youtube.com/watch?v=abc123"
    )
    print(f"Test 2 (risky source): passed={result.passed}, issues={result.issues}")
    
    # Test 3: Risky keywords
    result = check_before_upload(
        title="Official Music Video Reaction",
        description="Check out this full song",
    )
    print(f"Test 3 (risky keywords): passed={result.passed}, warnings={result.warnings}")
    
    print("\nAll tests completed!")
