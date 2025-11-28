# Python, Django, DRF Code Conventions

이 문서는 `job-crawler-be` 프로젝트의 코드 컨벤션을 정의합니다. 모든 기여자는 이 가이드라인을 따라야 합니다.

## 1. General Python

### 1.1 Formatting & Linting
- **Formatter**: `black`을 사용합니다.
  - Line Length: **100** characters
  - Python Version: **3.13** target
- **Import Sorting**: `isort`를 사용합니다.
  - Profile: `black`
- **Linting**: `pylint`를 사용하며, `pylint-django` 플러그인을 활성화합니다.
- **Pre-commit**: 커밋 전 `pre-commit` 훅이 자동으로 실행되어 포맷팅을 검사합니다.

### 1.2 Naming Conventions
- **Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_CASE`
- **Private Members**: `_leading_underscore`

### 1.3 Type Hinting
- 모든 함수와 메서드 시그니처에 Type Hint를 적극적으로 사용합니다.
- `typing` 모듈의 `List`, `Dict`, `Optional` 등을 활용하여 명시적으로 작성합니다.

```python
def process_data(self, user_id: int, data: Dict[str, Any]) -> Optional[Resume]:
    ...
```

### 1.4 Docstrings
- 클래스와 주요 메서드에는 Docstring을 작성합니다.
- Google Style 또는 간결한 설명을 사용합니다.

---

## 2. Django

### 2.1 Models
- **Field Definition**: 필드는 모델 클래스 상단에 정의합니다.
- **Meta Class**: `db_table`을 명시하여 테이블 이름을 지정합니다.
- **Methods**: `__str__`을 반드시 정의합니다. 데이터 상태와 관련된 로직(예: 해시 계산)은 모델 메서드로 구현합니다.
- **Save Override**: 데이터 무결성이나 자동 계산이 필요한 경우 `save()` 메서드를 오버라이드합니다.

```python
class Resume(models.Model):
    user = models.ForeignKey(...)
    title = models.CharField(...)

    class Meta:
        db_table = "agent_resume"

    def __str__(self):
        return f"{self.title} ({self.user_id})"
```

### 2.2 Service Layer Pattern
- **Business Logic**: 비즈니스 로직은 View가 아닌 **Service Layer**(`services.py`)에 작성합니다.
- **Transaction**: 트랜잭션 관리는 Service 메서드 내에서 `with transaction.atomic():`을 사용하여 처리합니다.
- **Static Methods**: 상태를 가지지 않는 로직은 `@staticmethod`로 정의하여 사용합니다.

```python
# services.py
class ResumeService:
    @staticmethod
    def create_resume(data: Dict) -> Resume:
        with transaction.atomic():
            # logic here
            return resume
```

---

## 3. Django Rest Framework (DRF)

### 3.1 Views (Thin Views)
- **ViewSets**: 가능한 경우 `ModelViewSet` 또는 `GenericViewSet`을 사용합니다.
- **Delegation**: View는 HTTP 요청/응답 처리, 권한 검사, 데이터 검증만 담당하고, 실제 처리는 Service에 위임합니다.
- **Exception Handling**: View 레벨에서 예외를 잡고 적절한 HTTP 상태 코드로 반환하며, 에러 로그를 남깁니다.

```python
# views.py
class ResumeViewSet(ModelViewSet):
    def create(self, request, *args, **kwargs):
        try:
            # Serializer validation
            # Service call
            return Response(...)
        except Exception as e:
            logger.error(...)
            return Response(...)
```

### 3.2 Serializers
- **ModelSerializer**: 모델 기반 데이터는 `ModelSerializer`를 사용합니다.
- **Fields**: `fields`를 명시적으로 나열하거나 `__all__`을 사용하되, `read_only_fields`를 적절히 설정합니다.
- **Endpoint Specific**: 각 Endpoint(Action)가 호출하는 함수명에 맞춰 Serializer를 분리하여 작성합니다.
  - 하나의 거대한 Serializer 대신, 각 Action의 목적에 맞는 전용 Serializer를 정의합니다.
  - 예: `create` -> `ResumeCreateSerializer`, `list` -> `ResumeListSerializer`, `retrieve` -> `ResumeDetailSerializer`

---

## 4. Async & Tasks

- **Celery**: 비동기 작업(LLM 분석, 외부 API 호출 등)은 Celery Task로 정의(`tasks.py`)하여 처리합니다.
- **Redis**: Celery Broker 및 Backend로 Redis를 사용합니다.

## 5. Environment Variables

- 설정값은 `os.getenv`를 사용하거나 `django.conf.settings`를 통해 접근합니다.
- 하드코딩된 비밀키나 설정값은 절대 코드에 포함하지 않습니다.
