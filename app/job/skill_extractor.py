"""
LLM-Free 스킬 추출기
정규식 패턴 매칭을 사용하여 텍스트에서 기술 스택을 추출합니다.
"""

import re
from functools import lru_cache
from typing import Dict, List, Set

# 마스터 스킬 목록 (name: patterns)
# patterns는 해당 스킬을 찾기 위한 정규식 패턴 리스트
MASTER_SKILLS: Dict[str, List[str]] = {
    # Backend Languages
    "Python": [r"python", r"파이썬"],
    "Java": [r"java(?!script)", r"자바(?!스크립트)"],
    "Kotlin": [r"kotlin", r"코틀린"],
    "Go": [r"golang", r"\bgo\b", r"go언어", r"고랭"],
    "Ruby": [r"ruby", r"루비"],
    "PHP": [r"php"],
    "C++": [r"c\+\+", r"cpp\b", r"씨플플"],
    "C#": [r"c#", r"c-?sharp", r"씨샵"],
    "C": [r"\bc언어\b", r"\bc\b(?!#|\+\+|pp)"],
    "Rust": [r"\brust\b", r"\b러스트\b"],
    "Scala": [r"\bscala\b", r"\b스칼라\b"],
    # Backend Frameworks
    "Django": [r"django", r"장고"],
    "Flask": [r"flask", r"플라스크"],
    "FastAPI": [r"fastapi", r"fast\s?api"],
    "Spring": [r"\bspring\b(?:\s?boot|\s?framework)?", r"\b스프링\b"],
    "Spring Boot": [r"\bspring\s?boot\b", r"\b스프링\s?부트\b"],
    "Express": [r"\bexpress(?:\.js)?\b", r"\b익스프레스\b"],
    "NestJS": [r"\bnestjs\b", r"\bnest\.js\b"],
    "Rails": [r"\bruby\s?on\s?rails\b", r"\brails\b", r"\b레일즈\b"],
    "Laravel": [r"\blaravel\b", r"\b라라벨\b"],
    "ASP.NET": [r"\basp\.net\b", r"\baspnet\b"],
    # Frontend Languages & Frameworks
    "JavaScript": [r"javascript", r"\bjs\b", r"자바스크립트"],
    "TypeScript": [r"typescript", r"\bts\b", r"타입스크립트"],
    "React": [r"react(?:\.js)?", r"리액트"],
    "Vue.js": [r"vue(?:\.js)?", r"뷰\.?js"],
    "Vue": [r"vue(?!\.js)", r"뷰(?!\.?js)"],
    "Angular": [r"\bangular\b", r"\b앵귤러\b"],
    "Svelte": [r"\bsvelte\b", r"\b스벨트\b"],
    "Next.js": [r"\bnext(?:\.js)?\b", r"\b넥스트\b"],
    "Nuxt.js": [r"\bnuxt(?:\.js)?\b", r"\b넉스트\b"],
    "jQuery": [r"\bjquery\b", r"\b제이쿼리\b"],
    # Mobile
    "React Native": [r"\breact\s?native\b", r"\b리액트\s?네이티브\b"],
    "Flutter": [r"\bflutter\b", r"\b플러터\b"],
    "Swift": [r"\bswift\b", r"\b스위프트\b"],
    "Objective-C": [r"\bobjective-?c\b", r"\b오브젝티브\s?c\b"],
    "Android": [r"\bandroid\b", r"\b안드로이드\b"],
    "iOS": [r"\bios\b", r"\b아이오에스\b"],
    # Databases
    "SQL": [r"\bsql\b"],
    "NoSQL": [r"\bnosql\b"],
    "MySQL": [r"\bmysql\b"],
    "PostgreSQL": [r"\bpostgresql\b", r"\bpostgres\b", r"\bpsql\b", r"\b포스트그레\b"],
    "MongoDB": [r"\bmongodb\b", r"\bmongo\b", r"\b몽고db\b"],
    "Redis": [r"\bredis\b", r"\b레디스\b"],
    "Elasticsearch": [r"\belasticsearch\b", r"\belastic\b", r"\b엘라스틱서치\b"],
    "Oracle": [r"\boracle\b", r"\b오라클\b"],
    "MS SQL": [r"\bms\s?sql\b", r"\bsql\s?server\b"],
    "MariaDB": [r"\bmariadb\b", r"\b마리아db\b"],
    "DynamoDB": [r"\bdynamodb\b", r"\b다이나모db\b"],
    "Cassandra": [r"\bcassandra\b", r"\b카산드라\b"],
    # Cloud & DevOps
    "AWS": [r"\baws\b", r"\bamazon\s?web\s?services\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle\s?cloud\b"],
    "Azure": [r"\bazure\b", r"\b애저\b"],
    "Docker": [r"\bdocker\b", r"\b도커\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b", r"\b쿠버네티스\b"],
    "Jenkins": [r"\bjenkins\b", r"\b젠킨스\b"],
    "GitHub Actions": [r"\bgithub\s?actions\b"],
    "GitLab CI": [r"\bgitlab\s?ci\b"],
    "Terraform": [r"\bterraform\b", r"\b테라폼\b"],
    "Ansible": [r"\bansible\b", r"\b앤서블\b"],
    "CircleCI": [r"\bcircleci\b", r"\b서클ci\b"],
    # Tools & Others
    "Git": [r"\bgit\b(?!hub|lab)", r"\b깃\b(?!허브|랩)"],
    "GitHub": [r"\bgithub\b", r"\b깃허브\b"],
    "GitLab": [r"\bgitlab\b", r"\b깃랩\b"],
    "Jira": [r"\bjira\b", r"\b지라\b"],
    "Confluence": [r"\bconfluence\b", r"\b컨플루언스\b"],
    "Slack": [r"\bslack\b", r"\b슬랙\b"],
    "Linux": [r"\blinux\b", r"\b리눅스\b"],
    "Unix": [r"\bunix\b", r"\b유닉스\b"],
    "GraphQL": [r"\bgraphql\b", r"\b그래프ql\b"],
    "REST API": [r"\brest\s?api\b", r"\brestful\b"],
    "gRPC": [r"\bgrpc\b"],
    "Kafka": [r"\bkafka\b", r"\b카프카\b"],
    "RabbitMQ": [r"\brabbitmq\b", r"\b래빗mq\b"],
    "Nginx": [r"\bnginx\b", r"\b엔진엑스\b"],
    "Apache": [r"\bapache\b(?!\s?spark)", r"\b아파치\b(?!\s?스파크)"],
    # Data & AI/ML
    "TensorFlow": [r"\btensorflow\b", r"\b텐서플로우\b"],
    "PyTorch": [r"\bpytorch\b", r"\b파이토치\b"],
    "Pandas": [r"\bpandas\b", r"\b판다스\b"],
    "NumPy": [r"\bnumpy\b", r"\b넘파이\b"],
    "scikit-learn": [r"\bscikit-?learn\b", r"\bsklearn\b"],
    "Spark": [r"\bspark\b", r"\b스파크\b"],
    "Hadoop": [r"\bhadoop\b", r"\b하둡\b"],
    "Airflow": [r"\bairflow\b", r"\b에어플로우\b"],
}


@lru_cache(maxsize=1)
def _get_compiled_patterns() -> Dict[str, List[re.Pattern]]:
    """
    스킬 패턴을 컴파일하여 캐시합니다.
    애플리케이션 수명 동안 한 번만 컴파일됩니다.
    """
    compiled = {}
    for skill_name, patterns in MASTER_SKILLS.items():
        compiled[skill_name] = [
            re.compile(pattern, re.IGNORECASE) for pattern in patterns
        ]
    return compiled


def extract_skills(text: str) -> List[str]:
    """
    주어진 텍스트에서 기술 스택을 추출합니다.

    Args:
        text: 분석할 텍스트 (공고 설명, 이력서 등)

    Returns:
        추출된 스킬 이름 리스트 (정렬됨)
    """
    if not text:
        return []

    # 텍스트 정규화
    normalized_text = text.lower()

    # 패턴 매칭
    found_skills: Set[str] = set()
    compiled_patterns = _get_compiled_patterns()

    for skill_name, patterns in compiled_patterns.items():
        for pattern in patterns:
            if pattern.search(normalized_text):
                found_skills.add(skill_name)
                break  # 하나의 패턴이라도 매치되면 다음 스킬로

    return sorted(list(found_skills))


def extract_skills_from_job_posting(
    requirements: str, preferred_points: str = "", main_tasks: str = ""
) -> tuple[List[str], str]:
    """
    채용 공고에서 필수 스킬과 우대 사항을 추출합니다.

    Args:
        requirements: 자격 요건 텍스트
        preferred_points: 우대 사항 텍스트
        main_tasks: 주요 업무 텍스트 (참고용)

    Returns:
        (필수 스킬 리스트, 우대 사항 원문) 튜플
    """
    # 필수 스킬: requirements + main_tasks에서 추출
    required_text = f"{requirements} {main_tasks}"
    skills_required = extract_skills(required_text)

    # 우대 사항: 원문에서 공백만 제거하여 저장
    skills_preferred_text = (
        " ".join(preferred_points.split()) if preferred_points else ""
    )

    return skills_required, skills_preferred_text


def get_all_skills() -> List[str]:
    """
    지원하는 모든 스킬 목록을 반환합니다.

    Returns:
        모든 스킬 이름 리스트 (정렬됨)
    """
    return sorted(list(MASTER_SKILLS.keys()))


def get_skill_count() -> int:
    """
    지원하는 스킬 개수를 반환합니다.
    """
    return len(MASTER_SKILLS)
