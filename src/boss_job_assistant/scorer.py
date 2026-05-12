import re
from typing import Iterable

from boss_job_assistant.models import JobPosting, ScoredJob


def parse_salary_lower_bound(salary: str) -> int:
    salary_text = str(salary or "")

    wan_match = re.search(
        r"(\d+(?:\.\d+)?)(?:\s*万)?(?:\s*-\s*\d+(?:\.\d+)?\s*万)?",
        salary_text,
    )
    if wan_match and "万" in wan_match.group(0):
        return int(float(wan_match.group(1)) * 10)

    k_match = re.search(
        r"(\d+)(?:\s*K)?(?:\s*-\s*\d+\s*K)?",
        salary_text,
        re.IGNORECASE,
    )
    if k_match and "K" in k_match.group(0).upper():
        return int(k_match.group(1))

    return 0


def parse_salary_upper_bound(salary: str) -> int:
    salary_text = str(salary or "")
    number_pattern = r"(\d+(?:\.\d+)?)"

    wan_range = re.search(
        rf"{number_pattern}\s*(?:万|æ¶“\?)?\s*[-~—–]\s*{number_pattern}\s*(?:万|æ¶“\?)",
        salary_text,
    )
    if wan_range:
        return int(float(wan_range.group(2)) * 10)

    wan_single = re.search(rf"{number_pattern}\s*(?:万|æ¶“\?)", salary_text)
    if wan_single:
        return int(float(wan_single.group(1)) * 10)

    k_range = re.search(
        rf"{number_pattern}\s*K?\s*[-~—–]\s*{number_pattern}\s*K",
        salary_text,
        re.IGNORECASE,
    )
    if k_range:
        return int(float(k_range.group(2)))

    k_single = re.search(rf"{number_pattern}\s*K", salary_text, re.IGNORECASE)
    if k_single:
        return int(float(k_single.group(1)))

    return 0


def parse_company_size(company_size: str) -> int:
    company_size_text = str(company_size or "")
    if not company_size_text or "少于" in company_size_text:
        return 0

    match = re.search(r"\d+", company_size_text)
    if not match:
        return 0
    return int(match.group(0))


def _is_latin_keyword(keyword: str) -> bool:
    return bool(re.search(r"[A-Za-z]", keyword))


def _contains_any(text: str, keywords: Iterable[str]) -> list[str]:
    normalized_text = str(text or "")
    hits = []

    for keyword in keywords:
        if not keyword:
            continue

        keyword_text = str(keyword)
        if _is_latin_keyword(keyword_text):
            pattern = (
                rf"(?<![A-Za-z0-9_]){re.escape(keyword_text)}"
                rf"(?![A-Za-z0-9_])"
            )
            if re.search(pattern, normalized_text, re.IGNORECASE):
                hits.append(keyword_text)
        elif keyword_text in normalized_text:
            hits.append(keyword_text)

    return hits


def score_job(job: JobPosting, config: dict) -> ScoredJob:
    filters = config.get("filters", {})
    scoring = config.get("scoring", {})

    combined_text = " ".join(
        [
            str(job.title or ""),
            str(job.salary or ""),
            str(job.location or ""),
            str(job.company or ""),
            str(job.industry or ""),
            str(job.company_size or ""),
            str(job.description or ""),
        ]
    )

    exclude_hits = _contains_any(combined_text, scoring.get("exclude_keywords", []))
    if exclude_hits:
        return ScoredJob(
            job=job,
            matched=False,
            score=0,
            exclusion_reason=f"命中排除关键词: {', '.join(exclude_hits)}",
        )

    required_location = str(filters.get("required_location", "") or "")
    job_location = str(job.location or "")
    if required_location and required_location not in job_location:
        return ScoredJob(
            job=job,
            matched=False,
            score=0,
            exclusion_reason=f"工作地不匹配: {job_location}",
        )

    min_salary_k = int(filters.get("min_salary_k", 0) or 0)
    salary_upper_bound = parse_salary_upper_bound(job.salary)
    if salary_upper_bound < min_salary_k:
        return ScoredJob(
            job=job,
            matched=False,
            score=0,
            exclusion_reason=f"薪资低于 {min_salary_k}K: {job.salary}",
        )

    min_company_size = int(filters.get("min_company_size", 0) or 0)
    company_size_lower_bound = parse_company_size(job.company_size)
    if company_size_lower_bound < min_company_size:
        return ScoredJob(
            job=job,
            matched=False,
            score=0,
            exclusion_reason=f"公司规模低于 {min_company_size}人: {job.company_size}",
        )

    score = 50
    matched_reasons = [
        f"薪资满足 {min_salary_k}K+",
        f"公司规模满足 {min_company_size}人+",
    ]

    positive_hits = _contains_any(combined_text, scoring.get("positive_keywords", []))
    if positive_hits:
        score += min(len(positive_hits) * 6, 30)
        matched_reasons.append(f"技术关键词: {', '.join(positive_hits)}")

    c_side_hits = _contains_any(combined_text, scoring.get("c_side_keywords", []))
    if c_side_hits:
        score += min(len(c_side_hits) * 5, 20)
        matched_reasons.append(f"C端关键词: {', '.join(c_side_hits)}")

    return ScoredJob(
        job=job,
        matched=True,
        score=min(score, 100),
        matched_reasons=matched_reasons,
    )
