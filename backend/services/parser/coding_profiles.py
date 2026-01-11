"""Coding profile extraction from resume text."""

import re
from typing import List
from dataclasses import dataclass, field


@dataclass
class CodingProfile:
    """A coding platform profile extracted from resume."""
    platform: str = ""
    username: str = ""
    problems_solved: int = 0
    rank: str = ""
    score: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "username": self.username,
            "problems_solved": self.problems_solved,
            "rank": self.rank,
            "score": self.score,
            "url": self.url,
        }


# Platform patterns
PLATFORM_PATTERNS = {
    "LeetCode": {
        "url_pattern": r"leetcode\.com/(?:u/)?([A-Za-z0-9_\-]+)",
        "text_pattern": r"LeetCode\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "CodeChef": {
        "url_pattern": r"codechef\.com/users/([A-Za-z0-9_\-]+)",
        "text_pattern": r"CodeChef\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "HackerRank": {
        "url_pattern": r"hackerrank\.com/(?:profile/)?([A-Za-z0-9_\-]+)",
        "text_pattern": r"HackerRank\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "HackerEarth": {
        "url_pattern": r"hackerearth\.com/@?([A-Za-z0-9_\-]+)",
        "text_pattern": r"HackerEarth\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "GeeksforGeeks": {
        "url_pattern": r"(?:geeksforgeeks\.org|gfg)/user/([A-Za-z0-9_\-]+)",
        "text_pattern": r"(?:GeeksforGeeks|GFG)\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "Codeforces": {
        "url_pattern": r"codeforces\.com/profile/([A-Za-z0-9_\-]+)",
        "text_pattern": r"Codeforces\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "TopCoder": {
        "url_pattern": r"topcoder\.com/members/([A-Za-z0-9_\-]+)",
        "text_pattern": r"TopCoder\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "AtCoder": {
        "url_pattern": r"atcoder\.jp/users/([A-Za-z0-9_\-]+)",
        "text_pattern": r"AtCoder\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "SPOJ": {
        "url_pattern": r"spoj\.com/users/([A-Za-z0-9_\-]+)",
        "text_pattern": r"SPOJ\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
    "OneCompiler": {
        "url_pattern": r"onecompiler\.com/([A-Za-z0-9_\-]+)",
        "text_pattern": r"OneCompil?er\s*:?\s*(?:Username:?\s*)?([A-Za-z0-9_\-]+)",
    },
}


def _extract_problems_solved(text: str, platform: str) -> int:
    """Extract problems solved count for a platform."""
    # Look for patterns like "Problems Solved: 250" or "250 problems"
    patterns = [
        rf"{platform}[^.]*?Problems?\s*Solved\s*:?\s*(\d+)",
        rf"{platform}[^.]*?(\d+)\s*(?:problems?|questions?)\s*solved",
        rf"{platform}[^.]*?,\s*Problems?\s*Solved\s*:?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return 0


def _extract_rank(text: str, platform: str) -> str:
    """Extract rank for a platform."""
    patterns = [
        rf"{platform}[^.]*?Rank\s*:?\s*([0-9,]+)",
        rf"{platform}[^.]*?Rating\s*:?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return ""


def _extract_score(text: str, platform: str) -> str:
    """Extract score for a platform."""
    pattern = rf"{platform}[^.]*?Score\s*:?\s*(\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def extract_coding_profiles(text: str) -> List[CodingProfile]:
    """Extract coding platform profiles from resume text.

    Looks for platform names, usernames, URLs, and statistics.

    Args:
        text: Raw resume text

    Returns:
        List of CodingProfile objects
    """
    profiles: List[CodingProfile] = []
    found_platforms = set()

    for platform, patterns in PLATFORM_PATTERNS.items():
        username = ""
        url = ""

        # Try URL pattern first
        url_match = re.search(patterns["url_pattern"], text, re.IGNORECASE)
        if url_match:
            username = url_match.group(1)
            # Reconstruct URL
            if platform == "LeetCode":
                url = f"https://leetcode.com/u/{username}"
            elif platform == "CodeChef":
                url = f"https://codechef.com/users/{username}"
            elif platform == "HackerRank":
                url = f"https://hackerrank.com/profile/{username}"
            elif platform == "GeeksforGeeks":
                url = f"https://geeksforgeeks.org/user/{username}"
            elif platform == "Codeforces":
                url = f"https://codeforces.com/profile/{username}"

        # Try text pattern if no URL found
        if not username:
            text_match = re.search(patterns["text_pattern"], text, re.IGNORECASE)
            if text_match:
                username = text_match.group(1)
                # Clean up username - remove trailing punctuation
                username = re.sub(r'[,;:\s]+$', '', username)

        if username and platform not in found_platforms:
            found_platforms.add(platform)

            profile = CodingProfile(
                platform=platform,
                username=username,
                problems_solved=_extract_problems_solved(text, platform),
                rank=_extract_rank(text, platform),
                score=_extract_score(text, platform),
                url=url,
            )
            profiles.append(profile)

    return profiles
