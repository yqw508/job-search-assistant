from boss_job_assistant.html_parser import parse_jobs_from_html


def test_parse_jobs_from_html_reads_boss_card():
    html = """
    <div class="job-card-wrapper">
      <a href="/job_detail/abc.html">
        <span class="job-name">Java 后端开发工程师</span>
        <span class="salary">25-35K</span>
        <span class="job-area">广州</span>
      </a>
      <ul class="tag-list"><li>5-10年</li><li>本科</li></ul>
      <div class="company-name">示例公司</div>
      <ul class="company-tag-list"><li>电商</li><li>B轮</li><li>100-499人</li></ul>
      <div>负责 C端 交易系统，技术栈 Java Spring Boot Redis MySQL。</div>
    </div>
    """

    jobs = parse_jobs_from_html(html)

    assert len(jobs) == 1
    assert jobs[0].title == "Java 后端开发工程师"
    assert jobs[0].salary == "25-35K"
    assert jobs[0].location == "广州"
    assert jobs[0].company == "示例公司"
    assert jobs[0].company_size == "100-499人"
    assert jobs[0].url == "https://www.zhipin.com/job_detail/abc.html"
    assert "Spring Boot" in jobs[0].description
