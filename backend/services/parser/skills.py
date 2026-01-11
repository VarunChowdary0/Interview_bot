"""Skills extraction from resume text."""

import re
from typing import List, Set


# Skill section headings
SKILL_HEADINGS = {
    'skills', 'technical skills', 'key skills', 'core competencies', 'expertise',
    'technologies', 'languages', 'programming languages', 'frameworks', 'libraries',
    'tools', 'tech stack', 'backend', 'frontend', 'data & storage', 'data and storage',
    'databases', 'messaging & streaming', 'messaging and streaming', 'cloud & devops',
    'cloud and devops', 'devops', 'testing & quality', 'testing and quality'
}

# Stop headings (non-skill sections)
STOP_HEADINGS = {
    'summary', 'experience', 'work experience', 'employment', 'work history',
    'internship', 'internships', 'projects', 'project', 'education', 'achievements',
    'awards', 'publications', 'interests', 'hobbies', 'certifications', 'training',
    'responsibilities'
}

# Known technology terms for validation - comprehensive list
TECH_BASE = {
    # Languages & runtimes
    'java', 'python', 'c', 'c++', 'c#', 'javascript', 'typescript', 'node.js', 'nodejs',
    'go', 'golang', 'rust', 'ruby', 'php', 'r', 'sql', 'kotlin', 'swift', 'scala',
    'bash', 'shell', 'powershell', 'perl', 'matlab', 'c/c++',
    # Frontend frameworks
    'react', 'react.js', 'reactjs', 'angular', 'vue', 'vue.js', 'next.js', 'nextjs',
    'nuxt', 'svelte', 'jquery', 'redux', 'tailwind', 'tailwind css', 'tailwindcss',
    'bootstrap', 'sass', 'scss', 'css', 'html', 'html5', 'css3',
    # Backend frameworks
    'fastapi', 'django', 'flask', 'spring', 'spring boot', 'express', 'express.js',
    'nest.js', 'nestjs', 'asp.net', '.net', 'rails', 'ruby on rails', 'laravel',
    'socket.io', 'koa', 'hapi',
    # Databases
    'mysql', 'postgres', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
    'dynamodb', 'sqlite', 'oracle', 'sql server', 'cassandra', 'firebase',
    'supabase', 'drizzle', 'drizzleorm', 'prisma', 'sequelize', 'typeorm',
    # Message queues
    'kafka', 'rabbitmq', 'sqs', 'redis', 'celery',
    # Cloud & DevOps
    'aws', 'ec2', 's3', 'lambda', 'cloudwatch', 'azure', 'gcp', 'google cloud',
    'kubernetes', 'k8s', 'docker', 'nginx', 'apache', 'heroku', 'vercel', 'netlify',
    'digitalocean', 'linode',
    # CI/CD & Version Control
    'git', 'github', 'gitlab', 'bitbucket', 'github actions', 'ci/cd', 'terraform',
    'ansible', 'jenkins', 'circleci', 'travis ci',
    # APIs & Auth
    'oauth2', 'oauth', 'jwt', 'openapi', 'swagger', 'rest', 'rest api', 'rest apis',
    'graphql', 'grpc', 'websocket', 'websockets', 'api development',
    # Testing
    'pytest', 'junit', 'jest', 'mocha', 'chai', 'cypress', 'selenium', 'postman',
    'locust', 'unittest',
    # Data Science & ML
    'pandas', 'numpy', 'scikit-learn', 'sklearn', 'tensorflow', 'pytorch', 'keras',
    'matplotlib', 'seaborn', 'opencv', 'nlp', 'machine learning', 'deep learning',
    'data science', 'jupyter', 'anaconda',
    # Mobile
    'react native', 'flutter', 'android', 'ios', 'swift', 'xcode', 'android studio',
    # Concepts
    'system design', 'data structures', 'algorithms', 'oop', 'concurrency',
    'multithreading', 'observability', 'logging', 'metrics', 'rate limiting',
    'idempotency', 'microservices', 'agile', 'agile development', 'scrum',
    'design patterns', 'solid', 'api design', 'rag',
}

# Generic terms to filter out
GENERIC_TERMS = {
    'basic', 'basics', 'clean', 'code', 'users', 'time', 'ready', 'facing',
    'performance', 'optimizations', 'patterns', 'data', 'models', 'documentation',
    'reviews', 'exposure', 'hooks', 'controls', 'cost', 'guardrails', 'campaign',
    'orchestration', 'front', 'back', 'end', 'present', 'current', 'internship',
    'internships', 'tools', 'concepts', 'core', 'learn', 'and', 'the', 'with',
    'for', 'using', 'via', 'features', 'enabling', 'techniques', 'real',
    'based', 'access', 'updates', 'push', 'notifications', 'rankings', 'contests',
    'powered', 'hints', 'accessible', 'professional', 'experience', 'coding',
    # Date-related
    '2020', '2021', '2022', '2023', '2024', '2025', '2026', '01', '02', '03',
    '04', '05', '06', '07', '08', '09', '10', '11', '12',
    # Location-related
    'hyderabad', 'telangana', 'india', 'bangalore', 'mumbai', 'delhi', 'chennai',
    # Common words that slip through
    'student', 'admin', 'supervisor', 'role', 'to', 'an',
}


def _normalize(s: str) -> str:
    """Normalize string for comparison."""
    return s.strip().lower().rstrip(':')


def _is_skill_heading(line: str) -> bool:
    """Check if line is a skill section heading."""
    normalized = _normalize(line)
    return any(normalized == h or normalized.startswith(h + ':') for h in SKILL_HEADINGS)


def _is_stop_heading(line: str) -> bool:
    """Check if line is a non-skill section heading."""
    normalized = _normalize(line)
    return any(normalized == h or normalized.startswith(h + ':') for h in STOP_HEADINGS)


def _looks_like_sentence(tok: str) -> bool:
    """Check if token looks like a sentence rather than a skill."""
    words = tok.split()
    if len(words) >= 6:
        return True
    if len(words) >= 4 and tok.endswith('.'):
        return True
    return False


def _is_acceptable_token(token: str) -> bool:
    """Check if token is an acceptable skill."""
    t = token.strip()
    if not t:
        return False

    low = t.lower()

    # Filter URLs and social profiles
    if any(bad in low for bad in ['linkedin', 'github.com', 'http', 'https', '@', '.com', '.app', '.io', 'vercel']):
        return False

    # Filter email patterns
    if re.search(r'\w+@\w+', t):
        return False

    # Filter generic terms
    if low in GENERIC_TERMS:
        return False

    # Filter if it's just numbers or dates
    if re.match(r'^[\d\s/\-]+$', t):
        return False

    # Filter page numbers like "1", "2", "1 / 2"
    if re.match(r'^\d+(\s*/\s*\d+)?$', t):
        return False

    # Limit words to reduce sentences
    words = t.split()
    if len(words) > 4:
        return False

    if _looks_like_sentence(t):
        return False

    # Reject if it looks like a certification fragment
    if any(phrase in low for phrase in ['freecodecamp', 'certification', 'certified', 'understanding of']):
        return False

    # Accept if in known tech base (exact match)
    if low in TECH_BASE:
        return True

    # Accept common tech name patterns (e.g., React.js, Node.js, C++, C#)
    if re.match(r'^[A-Z][a-z]*\.?(?:js|JS)$', t):  # React.js, Vue.js
        return True
    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$', t) and len(t) <= 20:  # Spring Boot, Tailwind CSS
        # Check if it looks like a tech term (capitalized words)
        if low in TECH_BASE or low.replace(' ', '') in TECH_BASE:
            return True

    # Accept if contains typical tech punctuation and is short
    if any(ch in t for ch in ['.', '#', '+']) and len(t) <= 15:
        return True

    # Reject very long single tokens (likely OCR glue)
    if len(t) > 20:
        return False

    # Accept single word tokens that look like tech terms
    if len(words) == 1:
        # Must start with letter, can contain letters/numbers/special chars
        if re.match(r'^[A-Za-z][A-Za-z0-9\+\#\.\-/]*$', t) and len(t) >= 2:
            # Reject if all lowercase and not in tech base (likely generic word)
            if t.islower() and low not in TECH_BASE:
                return False
            return True

    # Accept two-word tokens if they look like tech terms
    if len(words) == 2:
        combined = low.replace(' ', '')
        if combined in TECH_BASE or low in TECH_BASE:
            return True
        # Both words should be capitalized or known tech terms
        if all(w[0].isupper() or w.lower() in TECH_BASE for w in words if w):
            return True

    return False


def _split_skill_tokens(raw: str) -> List[str]:
    """Split raw text into individual skill tokens."""
    part = raw

    # Remove leading label if it's a heading
    if ':' in part:
        left, right = part.split(':', 1)
        if _normalize(left) in SKILL_HEADINGS:
            part = right

    # Split by common separators and bullets
    chunks = re.split(r'[\u2022\•\-\*\>|,;/\|]+', part)

    out: List[str] = []
    for ch in chunks:
        token = ch.strip()
        if _is_acceptable_token(token):
            out.append(token)

    return out


def extract_skills(text: str) -> List[str]:
    """Extract skills from resume text.

    Scans skill-related headings and stops at non-skill sections.
    Filters out generic words, sentences, and URLs.

    Args:
        text: Raw resume text

    Returns:
        List of extracted skills (deduplicated, order preserved)
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    collected: List[str] = []

    # Method 1: Section-based extraction
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _is_skill_heading(line):
            j = i + 1
            block: List[str] = []
            while j < n:
                next_line = lines[j]
                if not next_line.strip():
                    break
                if _is_skill_heading(next_line) or _is_stop_heading(next_line):
                    break
                block.append(next_line)
                j += 1
            for bl in block:
                collected.extend(_split_skill_tokens(bl))
            i = j
        else:
            i += 1

    # Method 2: Regex fallback for SKILLS blocks
    pattern = re.compile(
        r'(?:SKILLS|TECHNICAL SKILLS|KEY SKILLS|CORE COMPETENCIES|EXPERTISE)'
        r'[\s\n:]+(.*?)(?:\n\s*\n|\n[A-Z][A-Z\s/\-&]+:|$)',
        re.IGNORECASE | re.DOTALL
    )
    for m in pattern.finditer(text):
        block = m.group(1)
        for line in block.splitlines():
            collected.extend(_split_skill_tokens(line))

    # Normalize & dedupe while preserving order
    seen: Set[str] = set()
    result: List[str] = []

    for item in collected:
        cleaned = item.strip().strip('•-*>()').strip(':').strip()
        if not cleaned:
            continue

        normalized = _normalize(cleaned)
        if normalized in SKILL_HEADINGS or normalized in STOP_HEADINGS:
            continue

        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)

    return result
