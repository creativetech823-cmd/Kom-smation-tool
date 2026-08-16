"""One-time, idempotent seed data for the Hooks library and official
Templates. Called from app startup — each table is only seeded if it is
currently empty, so re-running after a partial manual wipe of one table
doesn't double-seed the other."""

from sqlalchemy.orm import Session

from app.db_models import Hook, Template, TemplateKind

CATEGORIES = [
    "Curiosity",
    "Problem",
    "Question",
    "Educational",
    "Storytelling",
    "Controversial",
    "FOMO",
    "Product",
    "Emotional",
    "Trending",
]

_GENERIC_TEMPLATES = [
    "Nobody tells you this about {topic}",
    "Stop doing this if you want {topic}",
    "3 things I wish I knew about {topic}",
    "You are probably making this mistake with {topic}",
]

_CATEGORY_SPECIFIC_TEMPLATES: dict[str, list[str]] = {
    "Curiosity": [
        "The secret nobody talks about with {topic}",
        "What if everything you knew about {topic} was wrong?",
        "Here's something weird about {topic} that changed everything",
    ],
    "Problem": [
        "The real reason {topic} isn't working for you",
        "Why {topic} keeps failing (and how to fix it)",
        "This is what's actually sabotaging {topic}",
    ],
    "Question": [
        "Are you making these mistakes with {topic}?",
        "What if I told you {topic} could be this simple?",
        "Have you ever wondered why {topic} feels so hard?",
    ],
    "Educational": [
        "Here's why {topic} actually works the way it does",
        "The science behind {topic}, explained simply",
        "What most people get wrong about {topic}",
    ],
    "Storytelling": [
        "I used to struggle with {topic} until this happened",
        "This one moment changed how I think about {topic}",
        "A year ago, {topic} was ruining my life — here's what changed",
    ],
    "Controversial": [
        "Unpopular opinion: everything you know about {topic} is wrong",
        "Nobody wants to admit this about {topic}",
        "The industry doesn't want you to know this about {topic}",
    ],
    "FOMO": [
        "Everyone is switching to this for {topic} — are you?",
        "Don't be the last one to figure out {topic}",
        "This is going viral for {topic} and here's why",
    ],
    "Product": [
        "This changed my {topic} completely",
        "I tried everything for {topic} until I found this",
        "The one thing that actually fixed {topic}",
    ],
    "Emotional": [
        "If you've ever felt alone dealing with {topic}, watch this",
        "This is for anyone who's tired of struggling with {topic}",
        "I finally feel in control of {topic} again",
    ],
    "Trending": [
        "Everyone's talking about this {topic} trend",
        "Why this {topic} hack is everywhere right now",
        "The {topic} trend that's actually worth trying",
    ],
}

_TOPICS = [
    "your skincare routine",
    "losing weight",
    "saving money",
    "building muscle",
    "your sleep schedule",
    "your morning routine",
    "your finances",
    "your diet",
]

_PLATFORMS = ["Instagram Reels", "TikTok", "YouTube Shorts", "Facebook", "General"]
_TONES = ["Bold", "Playful", "Serious", "Empathetic", "Urgent"]


def _generate_hooks() -> list[dict]:
    rows: list[dict] = []
    i = 0
    for category in CATEGORIES:
        templates = _GENERIC_TEMPLATES + _CATEGORY_SPECIFIC_TEMPLATES[category]
        for template in templates:
            for topic in _TOPICS:
                rows.append(
                    {
                        "text": template.format(topic=topic),
                        "category": category,
                        "platform": _PLATFORMS[i % len(_PLATFORMS)],
                        "tone": _TONES[i % len(_TONES)],
                    }
                )
                i += 1
    return rows


_STATIC_TEMPLATES = [
    ("Instagram Post", "Social Media", "gradient-purple-teal", "A clean single-image post sized for the Instagram feed."),
    ("Instagram Story", "Social Media", "gradient-magenta-indigo", "Full-screen vertical layout built for Stories/Reels covers."),
    ("Product Advertisement", "Advertising", "gradient-teal-indigo", "A bold, benefit-led static ad layout for a single hero product."),
    ("Promotional Banner", "Advertising", "gradient-magenta-purple", "Wide banner layout for sales, launches, and promo callouts."),
    ("Quote Post", "Engagement", "gradient-purple-magenta", "Typography-forward layout for a testimonial or brand quote."),
    ("Product Showcase", "Catalog", "gradient-indigo-teal", "Grid-style layout for showing a product from multiple angles."),
]

_VIDEO_TEMPLATES = [
    ("Product Advertisement", "Advertising", "gradient-teal-purple", "Fast-paced, benefit-driven product ad structure."),
    ("UGC Style", "Authentic", "gradient-magenta-teal", "Handheld, testimonial-style pacing that mimics organic creator content."),
    ("Product Showcase", "Catalog", "gradient-indigo-magenta", "Slow, detail-focused shots that highlight product craftsmanship."),
    ("Cinematic", "Premium", "gradient-purple-indigo", "Moody, high-production pacing with dramatic lighting cues."),
    ("Educational", "Explainer", "gradient-teal-magenta", "Clear, step-by-step structure for how-it-works style videos."),
    ("Promotional", "Advertising", "gradient-magenta-indigo", "High-energy structure built around a sale or limited-time offer."),
    ("Testimonial", "Authentic", "gradient-purple-teal", "Customer-voice-led structure built around a real result/story."),
    ("Before / After", "Transformation", "gradient-indigo-purple", "Split-structure video built around a clear transformation arc."),
]


def _seed_hooks(db: Session) -> None:
    if db.query(Hook).count() > 0:
        return
    rows = _generate_hooks()
    db.bulk_insert_mappings(Hook, rows)
    db.commit()


def _seed_templates(db: Session) -> None:
    if db.query(Template).count() > 0:
        return
    rows = []
    for name, category, thumbnail_key, description in _STATIC_TEMPLATES:
        rows.append(
            {
                "name": name,
                "kind": TemplateKind.static,
                "category": category,
                "description": description,
                "thumbnail_key": thumbnail_key,
                "is_official": True,
            }
        )
    for name, category, thumbnail_key, description in _VIDEO_TEMPLATES:
        rows.append(
            {
                "name": name,
                "kind": TemplateKind.video,
                "category": category,
                "description": description,
                "thumbnail_key": thumbnail_key,
                "is_official": True,
            }
        )
    db.bulk_insert_mappings(Template, rows)
    db.commit()


def seed_if_empty(db: Session) -> None:
    _seed_hooks(db)
    _seed_templates(db)
