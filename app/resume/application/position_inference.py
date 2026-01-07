from __future__ import annotations


def infer_position_from_skills(skills: list[str]) -> str:
    """
    스킬 목록을 기반으로 추천 포지션을 간단히 추론합니다.

    - LLM이 실패하거나 position을 비워서 반환하는 경우를 보완하기 위한 규칙 기반 추론입니다.
    - 정확도보다 "빈 값 방지"와 "설명 가능성"을 우선합니다.
    """
    if not skills:
        return ""

    skill_set = set(skills)

    backend = {
        "Django",
        "Flask",
        "FastAPI",
        "Spring",
        "Spring Boot",
        "NestJS",
        "Express",
        "Rails",
        "Laravel",
        "ASP.NET",
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "Redis",
        "Kafka",
        "RabbitMQ",
        "REST API",
        "GraphQL",
    }
    frontend = {
        "React",
        "Vue",
        "Vue.js",
        "Angular",
        "Svelte",
        "Next.js",
        "Nuxt.js",
        "JavaScript",
        "TypeScript",
    }
    devops = {
        "AWS",
        "GCP",
        "Azure",
        "Docker",
        "Kubernetes",
        "Terraform",
        "Ansible",
        "Jenkins",
        "GitHub Actions",
        "GitLab CI",
        "Prometheus",
        "Grafana",
    }
    data_ml = {
        "PyTorch",
        "TensorFlow",
        "scikit-learn",
        "Pandas",
        "NumPy",
        "Spark",
        "Hadoop",
        "Airflow",
        "MLflow",
    }
    mobile = {
        "Android",
        "iOS",
        "Kotlin",
        "Swift",
        "React Native",
        "Flutter",
    }

    if skill_set & backend:
        return "백엔드 개발자"
    if skill_set & frontend:
        return "프론트엔드 개발자"
    if skill_set & data_ml:
        return "데이터/머신러닝 엔지니어"
    if skill_set & devops:
        return "DevOps/인프라 엔지니어"
    if skill_set & mobile:
        return "모바일 앱 개발자"

    if {"Python", "Java", "Go", "C#", "C++"} & skill_set:
        return "백엔드 개발자"
    if {"JavaScript", "TypeScript"} & skill_set:
        return "프론트엔드 개발자"

    return ""
