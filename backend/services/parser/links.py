"""Social and professional links extraction from resume text."""

import re
from typing import Dict
from dataclasses import dataclass, field


@dataclass
class SocialLinks:
    """Social and professional links extracted from resume."""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    twitter: str = ""
    website: str = ""
    other: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "linkedin": self.linkedin,
            "github": self.github,
            "portfolio": self.portfolio,
            "twitter": self.twitter,
            "website": self.website,
            "other": self.other,
        }


def _normalize_url(url: str) -> str:
    """Normalize URL to include https:// prefix."""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    # Remove trailing slashes
    url = url.rstrip('/')
    return url


def extract_links(text: str) -> SocialLinks:
    """Extract social and professional links from resume text.

    Looks for LinkedIn, GitHub, portfolio, Twitter, and other links.

    Args:
        text: Raw resume text

    Returns:
        SocialLinks object with extracted URLs
    """
    links = SocialLinks()

    # LinkedIn
    linkedin_match = re.search(
        r'(?:linkedin\.com/in/|linkedin:\s*)([\w\-]+)',
        text, re.IGNORECASE
    )
    if linkedin_match:
        username = linkedin_match.group(1)
        links.linkedin = f"https://linkedin.com/in/{username}"

    # GitHub
    github_match = re.search(
        r'(?:github\.com/|github:\s*)([\w\-]+)',
        text, re.IGNORECASE
    )
    if github_match:
        username = github_match.group(1)
        # Avoid matching common non-username patterns
        if username.lower() not in ('com', 'io', 'org', 'pages'):
            links.github = f"https://github.com/{username}"

    # Twitter/X
    twitter_match = re.search(
        r'(?:twitter\.com/|x\.com/|twitter:\s*|@)([\w]+)',
        text, re.IGNORECASE
    )
    if twitter_match:
        username = twitter_match.group(1)
        # Avoid email @ symbols
        if '@' not in text[max(0, twitter_match.start()-1):twitter_match.start()]:
            if username.lower() not in ('gmail', 'yahoo', 'hotmail', 'outlook'):
                links.twitter = f"https://twitter.com/{username}"

    # Portfolio/Personal Website
    # Look for common portfolio platforms
    portfolio_patterns = [
        r'([\w\-]+\.(?:vercel|netlify|github\.io|surge\.sh|herokuapp|render)\.(?:app|com|io)[/\w\-]*)',
        r'(?:portfolio|website|site|blog)[\s:]+([a-zA-Z0-9\-]+\.[a-zA-Z]{2,}[/\w\-]*)',
    ]

    for pattern in portfolio_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            links.portfolio = _normalize_url(match.group(1))
            break

    # Generic website detection (personal domains)
    website_match = re.search(
        r'(?:website|site|web)[\s:]+(?:https?://)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,}[/\w\-]*)',
        text, re.IGNORECASE
    )
    if website_match and not links.portfolio:
        links.website = _normalize_url(website_match.group(1))

    # Other platforms
    other_platforms = {
        'Medium': r'medium\.com/@?([\w\-]+)',
        'Dev.to': r'dev\.to/([\w\-]+)',
        'Hashnode': r'hashnode\.com/@?([\w\-]+)',
        'Dribbble': r'dribbble\.com/([\w\-]+)',
        'Behance': r'behance\.net/([\w\-]+)',
        'StackOverflow': r'stackoverflow\.com/users/(\d+)',
        'Kaggle': r'kaggle\.com/([\w\-]+)',
        'YouTube': r'youtube\.com/(?:@|c(?:hannel)?/)?([\w\-]+)',
    }

    for platform, pattern in other_platforms.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            username = match.group(1)
            if platform == 'StackOverflow':
                links.other[platform] = f"https://stackoverflow.com/users/{username}"
            elif platform == 'YouTube':
                links.other[platform] = f"https://youtube.com/@{username}"
            else:
                domain = platform.lower().replace('.', '')
                if platform == 'Dev.to':
                    links.other[platform] = f"https://dev.to/{username}"
                elif platform == 'Medium':
                    links.other[platform] = f"https://medium.com/@{username}"
                else:
                    links.other[platform] = f"https://{platform.lower()}.com/{username}"

    return links
