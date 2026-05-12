from dataclasses import dataclass, field


@dataclass(slots=True)
class JobPosting:
    title: str = ""
    salary: str = ""
    location: str = ""
    experience: str = ""
    education: str = ""
    company: str = ""
    industry: str = ""
    financing: str = ""
    company_size: str = ""
    source: str = "boss"
    source_job_id: str = ""
    source_url: str = ""
    url: str = ""
    description: str = ""


@dataclass(slots=True)
class ScoredJob:
    job: JobPosting
    matched: bool
    score: int
    matched_reasons: list[str] = field(default_factory=list)
    exclusion_reason: str = ""
