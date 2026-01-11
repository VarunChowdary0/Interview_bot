"""Project extraction from resume text."""

import re
from typing import List
from dataclasses import dataclass, field


@dataclass
class Project:
    """A single project extracted from resume."""
    name: str = ""
    description: str = ""
    technologies: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "technologies": self.technologies,
        }


# Common technology keywords to extract from project descriptions
TECH_KEYWORDS = {
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "ruby", "go", "golang",
    "rust", "php", "swift", "kotlin", "scala", "r", "matlab", "perl", "c",
    # Frontend
    "react", "angular", "vue", "vue.js", "next.js", "nextjs", "nuxt", "svelte",
    "html", "css", "sass", "scss", "tailwind", "tailwindcss", "bootstrap", "jquery",
    # Backend
    "node.js", "nodejs", "express", "express.js", "django", "flask", "fastapi",
    "spring", "spring boot", "rails", "laravel", "asp.net", ".net",
    # Databases
    "mongodb", "mysql", "postgresql", "postgres", "redis", "sqlite", "oracle",
    "cassandra", "dynamodb", "firebase", "supabase", "tursodb",
    # Cloud/DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "jenkins", "terraform",
    "ansible", "nginx", "apache", "heroku", "vercel", "netlify",
    # ML/AI
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "opencv", "machine learning", "deep learning", "nlp", "computer vision",
    # Tools/Protocols
    "git", "github", "gitlab", "websocket", "websockets", "webrtc", "rest", "graphql",
    "grpc", "kafka", "rabbitmq", "elasticsearch",
    # Mobile
    "react native", "flutter", "android", "ios", "swift", "xcode",
    # Other
    "mern", "mern stack", "mean", "mean stack", "jupyter", "openai", "api", "apis",
}


def _extract_technologies(text: str) -> List[str]:
    """Extract technology keywords from text."""
    text_lower = text.lower()
    found = []

    # Sort by length descending to match longer terms first (e.g., "react native" before "react")
    sorted_keywords = sorted(TECH_KEYWORDS, key=len, reverse=True)

    for tech in sorted_keywords:
        # Use word boundary matching
        pattern = r'\b' + re.escape(tech) + r'\b'
        if re.search(pattern, text_lower):
            # Normalize the technology name
            normalized = tech.title() if len(tech) > 3 else tech.upper()
            # Handle special cases
            if tech in ("node.js", "nodejs"):
                normalized = "Node.js"
            elif tech in ("next.js", "nextjs"):
                normalized = "Next.js"
            elif tech in ("vue.js",):
                normalized = "Vue.js"
            elif tech in ("express.js",):
                normalized = "Express.js"
            elif tech in ("react native",):
                normalized = "React Native"
            elif tech in ("mern stack", "mern"):
                normalized = "MERN Stack"
            elif tech in ("mean stack", "mean"):
                normalized = "MEAN Stack"
            elif tech in ("spring boot",):
                normalized = "Spring Boot"
            elif tech in ("machine learning",):
                normalized = "Machine Learning"
            elif tech in ("deep learning",):
                normalized = "Deep Learning"
            elif tech in ("scikit-learn",):
                normalized = "Scikit-Learn"
            elif tech in ("tailwindcss", "tailwind"):
                normalized = "TailwindCSS"
            elif tech in ("websocket", "websockets"):
                normalized = "WebSockets"
            elif tech in ("webrtc",):
                normalized = "WebRTC"
            elif tech in ("graphql",):
                normalized = "GraphQL"
            elif tech in ("mongodb",):
                normalized = "MongoDB"
            elif tech in ("mysql",):
                normalized = "MySQL"
            elif tech in ("postgresql", "postgres"):
                normalized = "PostgreSQL"
            elif tech in ("fastapi",):
                normalized = "FastAPI"

            if normalized not in found:
                found.append(normalized)

    return found


def _clean_project_name(name: str) -> str:
    """Clean and normalize project name."""
    # Remove leading bullets, dashes, numbers
    name = re.sub(r'^[\s•\-*>\d.)+]+', '', name)
    # Remove trailing colons, dashes
    name = re.sub(r'[\s:\-]+$', '', name)
    # Clean up whitespace
    name = ' '.join(name.split())
    return name.strip()


def _clean_description(desc: str) -> str:
    """Clean and normalize project description."""
    # Remove leading/trailing whitespace and punctuation
    desc = desc.strip(' .,;:-')
    # Clean up whitespace
    desc = ' '.join(desc.split())
    return desc


def extract_projects(text: str) -> List[Project]:
    """Extract projects from resume text.

    Looks for a Projects section and parses individual project entries.
    Each project typically has a name followed by a colon and description.

    Args:
        text: Raw resume text

    Returns:
        List of Project objects
    """
    projects: List[Project] = []

    # Find projects section - look for various headers
    projects_section = re.search(
        r'(?:^|\n)\s*(?:PROJECTS?|PERSONAL PROJECTS?|ACADEMIC PROJECTS?|'
        r'KEY PROJECTS?|SIDE PROJECTS?|PORTFOLIO)\s*:?[\t ]*\n'
        r'(.*?)(?=\n\s*(?:EDUCATION|SKILLS|EXPERIENCE|WORK|EMPLOYMENT|'
        r'CERTIFICATIONS?|CERTIFICATES?|ACHIEVEMENTS?|PUBLICATIONS?|'
        r'LANGUAGES?|SUMMARY|ABOUT|INTERESTS?|HOBBIES?|LEADERSHIP|'
        r'INTERNSHIPS?|AWARDS?|REFERENCES?)\b|$)',
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if not projects_section:
        return projects

    section_text = projects_section.group(1)
    lines = section_text.split('\n')

    current_project = None
    current_description_parts = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this line starts a new project
        # Projects typically start with a bullet or name followed by colon
        project_start = re.match(
            r'^[•\-*>]?\s*([A-Za-z][A-Za-z0-9\s\.\-_&]+?)\s*:\s*(.*)$',
            line
        )

        if project_start:
            # Save previous project if exists
            if current_project and current_project.name:
                full_desc = ' '.join(current_description_parts)
                current_project.description = _clean_description(full_desc)
                current_project.technologies = _extract_technologies(
                    current_project.name + ' ' + current_project.description
                )
                projects.append(current_project)

            # Start new project
            name = _clean_project_name(project_start.group(1))
            desc_start = project_start.group(2).strip()

            current_project = Project(name=name)
            current_description_parts = [desc_start] if desc_start else []

        elif current_project:
            # This is a continuation line for the current project
            # Skip lines that look like sub-bullets with just technologies
            if re.match(r'^[◦○▪▸]\s*', line):
                # Sub-bullet, likely additional details
                cleaned = re.sub(r'^[◦○▪▸]\s*', '', line)
                current_description_parts.append(cleaned)
            elif not re.match(r'^[•\-*>]\s*[A-Z]', line):
                # Continuation of description
                current_description_parts.append(line)

    # Don't forget the last project
    if current_project and current_project.name:
        full_desc = ' '.join(current_description_parts)
        current_project.description = _clean_description(full_desc)
        current_project.technologies = _extract_technologies(
            current_project.name + ' ' + current_project.description
        )
        projects.append(current_project)

    return projects
