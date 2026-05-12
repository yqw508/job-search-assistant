from boss_job_assistant.models import JobPosting
from boss_job_assistant.scorer import parse_company_size, parse_salary_lower_bound, score_job


CONFIG = {
    "filters": {
        "min_salary_k": 22,
        "min_company_size": 100,
        "required_location": "广州",
    },
    "scoring": {
        "positive_keywords": ["Java", "Spring Boot", "Redis", "MySQL", "高并发"],
        "c_side_keywords": ["C端", "电商", "交易", "支付", "会员"],
        "exclude_keywords": ["外包", "驻场", "派遣", "外派"],
    },
}


def test_parse_salary_lower_bound():
    assert parse_salary_lower_bound("22-35K·14薪") == 22
    assert parse_salary_lower_bound("30-45K") == 30
    assert parse_salary_lower_bound("25K-35K") == 25
    assert parse_salary_lower_bound("2-3万") == 20
    assert parse_salary_lower_bound("1.5-2万") == 15
    assert parse_salary_lower_bound("1.8万-2.5万") == 18
    assert parse_salary_lower_bound("薪资面议") == 0


def test_parse_company_size():
    assert parse_company_size("100-499人") == 100
    assert parse_company_size("1000-9999人") == 1000
    assert parse_company_size("少于15人") == 0
    assert parse_company_size("0-20人") == 0
    assert parse_company_size("公司规模未知") == 0


def test_score_job_accepts_strong_c_side_match():
    job = JobPosting(
        title="Java 后端开发工程师",
        salary="25-35K",
        location="广州",
        company_size="100-499人",
        description="负责 C端 电商 交易系统，技术栈 Java Spring Boot Redis MySQL 高并发。",
    )

    scored_job = score_job(job, CONFIG)

    assert scored_job.matched is True
    assert scored_job.score >= 80
    assert "薪资满足 22K+" in scored_job.matched_reasons
    assert scored_job.exclusion_reason == ""


def test_score_job_rejects_outsourcing():
    job = JobPosting(
        title="Java 外包开发",
        salary="25-35K",
        location="广州",
        company_size="100-499人",
        description="外包项目，负责 Java 开发。",
    )

    scored_job = score_job(job, CONFIG)

    assert scored_job.matched is False
    assert "外包" in scored_job.exclusion_reason


def test_latin_keyword_does_not_match_inside_larger_word():
    config = {
        "filters": {
            "min_salary_k": 22,
            "min_company_size": 100,
            "required_location": "广州",
        },
        "scoring": {
            "positive_keywords": ["Java"],
            "c_side_keywords": ["App"],
            "exclude_keywords": [],
        },
    }
    job = JobPosting(
        title="前端开发工程师",
        salary="25-35K",
        location="广州",
        company_size="100-499人",
        description="JavaScript App",
    )

    scored_job = score_job(job, config)

    assert "技术关键词: Java" not in scored_job.matched_reasons
