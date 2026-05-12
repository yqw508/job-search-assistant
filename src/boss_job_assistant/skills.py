import re
from typing import Any


SKILL_TAXONOMY: tuple[dict[str, Any], ...] = (
    {"name": "Java", "category": "编程语言", "aliases": ["Java", "JDK", "Java8", "Java17"]},
    {"name": "Spring Boot", "category": "后端框架", "aliases": ["Spring Boot", "SpringBoot"]},
    {"name": "Spring Cloud", "category": "微服务", "aliases": ["Spring Cloud", "SpringCloud"]},
    {"name": "MyBatis", "category": "后端框架", "aliases": ["MyBatis", "Mybatis"]},
    {"name": "Dubbo", "category": "微服务", "aliases": ["Dubbo"]},
    {"name": "MySQL", "category": "数据库", "aliases": ["MySQL"]},
    {"name": "Redis", "category": "缓存", "aliases": ["Redis"]},
    {"name": "Kafka", "category": "消息队列", "aliases": ["Kafka"]},
    {"name": "RocketMQ", "category": "消息队列", "aliases": ["RocketMQ", "Rocket MQ"]},
    {"name": "RabbitMQ", "category": "消息队列", "aliases": ["RabbitMQ", "Rabbit MQ"]},
    {"name": "MQ", "category": "消息队列", "aliases": ["MQ", "消息队列"]},
    {"name": "微服务", "category": "架构能力", "aliases": ["微服务"]},
    {"name": "分布式技术", "category": "架构能力", "aliases": ["分布式技术", "分布式架构", "分布式"]},
    {"name": "架构设计", "category": "架构能力", "aliases": ["架构设计", "平台架构", "系统架构", "架构图"]},
    {"name": "技术架构师", "category": "岗位能力", "aliases": ["技术架构师", "架构师"]},
    {"name": "后端开发", "category": "岗位能力", "aliases": ["后端开发", "后端"]},
    {"name": "高并发", "category": "架构能力", "aliases": ["高并发", "并发"]},
    {"name": "JVM", "category": "Java 基础", "aliases": ["JVM", "虚拟机"]},
    {"name": "JVM 调优", "category": "Java 基础", "aliases": ["JVM调优", "JVM 调优", "故障排查"]},
    {"name": "多线程", "category": "Java 基础", "aliases": ["多线程", "线程池"]},
    {"name": "数据库优化", "category": "数据库", "aliases": ["SQL优化", "数据库优化", "索引优化", "慢 SQL"]},
    {"name": "分布式事务", "category": "架构能力", "aliases": ["分布式事务", "事务一致性"]},
    {"name": "DDD", "category": "架构能力", "aliases": ["DDD", "领域驱动"]},
    {"name": "Docker", "category": "工程效率", "aliases": ["Docker", "容器"]},
    {"name": "Kubernetes", "category": "工程效率", "aliases": ["Kubernetes", "K8S", "k8s"]},
    {"name": "容器技术", "category": "工程效率", "aliases": ["容器技术", "容器化"]},
    {"name": "Service Mesh", "category": "微服务", "aliases": ["Service Mesh", "ServiceMesh"]},
    {"name": "ElasticSearch", "category": "搜索", "aliases": ["ElasticSearch", "Elasticsearch", "ES"]},
    {"name": "C端业务", "category": "业务经验", "aliases": ["C端", "用户端", "消费者端", "ToC", "to C"]},
    {"name": "交易系统", "category": "业务经验", "aliases": ["交易", "订单", "支付", "营销"]},
    {"name": "医疗信息化", "category": "业务经验", "aliases": ["医疗信息化", "医疗管理平台", "医联体", "医共体", "医疗软件", "电子病历"]},
    {"name": "医疗数据标准", "category": "业务经验", "aliases": ["医疗业务流", "数据标准", "电子病历评级", "互联互通四级"]},
    {"name": "生成式 AI", "category": "AI 能力", "aliases": ["生成式AI", "生成式 AI", "AI助手", "专家知识库"]},
    {"name": "技术管理", "category": "管理能力", "aliases": ["技术管理", "Java开发团队", "团队交付", "复杂系统交付"]},
    {"name": "多机构系统落地", "category": "架构能力", "aliases": ["多机构系统落地", "多机构", "多家以上医疗机构", "架构落地", "从0到1架构"]},
)

PRIORITY_HEADING_PATTERN = re.compile(
    r"(优先录用|加分项|优先考虑|优先|加分|额外要求|亮点|bonus)",
    re.IGNORECASE,
)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if re.search(r"[A-Za-z]", alias):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _context_for_match(text: str, start: int, end: int) -> str:
    left = max(0, start - 48)
    right = min(len(text), end + 48)
    context = text[left:right]
    return re.sub(r"\s+", " ", context).strip()


def _split_weighted_sections(description: str) -> list[tuple[str, int]]:
    sections: list[tuple[str, int]] = []
    current_weight = 1
    buffer: list[str] = []

    for raw_line in description.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading_match = PRIORITY_HEADING_PATTERN.search(line)
        if heading_match:
            if buffer:
                sections.append(("\n".join(buffer), current_weight))
                buffer = []
            current_weight = 3
            tail = line[heading_match.end() :].strip(" ：:;；")
            if tail:
                buffer.append(tail)
            continue
        buffer.append(line)

    if buffer:
        sections.append(("\n".join(buffer), current_weight))
    return sections or [(description, 1)]


def extract_skill_mentions(job: dict[str, Any]) -> list[dict[str, Any]]:
    title_text = str(job.get("title", "") or "")
    description = str(job.get("description", "") or "")
    base_text = " ".join(str(job.get(field, "") or "") for field in ("matched_reasons", "industry"))
    weighted_sections = [(title_text, 2), (base_text, 1), *_split_weighted_sections(description)]
    mentions: list[dict[str, Any]] = []

    for skill in SKILL_TAXONOMY:
        contexts: list[str] = []
        raw_count = 0
        weighted_count = 0
        priority_hit = False
        for text, weight in weighted_sections:
            if not text:
                continue
            for alias in skill["aliases"]:
                for match in _alias_pattern(str(alias)).finditer(text):
                    raw_count += 1
                    weighted_count += weight
                    priority_hit = priority_hit or weight >= 3
                    context = _context_for_match(text, match.start(), match.end())
                    if context and context not in contexts:
                        contexts.append(context)
        if raw_count:
            mentions.append(
                {
                    "name": skill["name"],
                    "category": skill["category"],
                    "mention_count": weighted_count,
                    "contexts": contexts[:3],
                    "importance": min(100, 45 + weighted_count * 12 + (20 if priority_hit else 0)),
                    "priority": priority_hit,
                }
            )

    return sorted(mentions, key=lambda item: (-int(item["importance"]), item["name"]))
