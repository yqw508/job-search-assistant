from boss_job_assistant.skills import extract_skill_mentions


def test_extract_skill_mentions_from_job_description():
    mentions = extract_skill_mentions(
        {
            "title": "Java 后端开发工程师",
            "description": "负责 Spring Boot 微服务开发，使用 Redis、MySQL、Kafka 支撑 C端交易系统高并发场景。",
            "industry": "互联网",
        }
    )

    names = {mention["name"] for mention in mentions}
    assert {"Java", "Spring Boot", "Redis", "MySQL", "Kafka", "C端业务", "交易系统", "高并发"} <= names


def test_extract_skill_mentions_prioritizes_bonus_sections():
    mentions = extract_skill_mentions(
        {
            "title": "技术架构师",
            "description": """
职位描述
容器技术 分布式技术 架构师 后端开发 Dubbo
硬性条件：
1、精通 Java 生态：Spring Cloud/Boot、MyBatis、Dubbo、RocketMQ，具备高并发场景下 JVM 调优与故障排查能力；
2、精通云原生与分布式架构（K8s/Docker/Service Mesh），有百万级用户系统高可用实战案例；
优先录用：
1、有区域慢病管理平台、医联体/医共体系统从0到1架构落地案例；
2、熟悉生成式AI在跨机构场景的应用，如医院专家知识库到社区AI助手联动；
3、具备技术管理能力：曾带领10人以上Java开发团队完成复杂系统交付。
""",
        }
    )

    by_name = {mention["name"]: mention for mention in mentions}
    assert {"技术架构师", "容器技术", "分布式技术", "Dubbo", "MyBatis", "RocketMQ", "JVM 调优"} <= set(by_name)
    assert {"医疗信息化", "生成式 AI", "技术管理", "多机构系统落地"} <= set(by_name)
    assert by_name["医疗信息化"]["priority"] is True
    assert by_name["生成式 AI"]["priority"] is True
    assert by_name["技术管理"]["priority"] is True
    assert by_name["技术管理"]["importance"] >= 80
