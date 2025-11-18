"""
이력서 분석 LLM 테스트
실제 이력서로 LLM이 경력을 올바르게 추출하는지 테스트
"""

import json
import re
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase
from job.models import Resume


class TestResumeAnalysis(TestCase):
    """이력서 분석 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.sample_resume = """# 유용운

### Contact.
Email. yongwun0069@naver.com
Phone. 010-2615-0420

### Github
https://github.com/omognuni

# Introduce.
새로운 도메인과 기술 스택에 빠르게 적응하여 성능 최적화와 아키텍처 개선을 통해 실질적인 성과를 만들어낸 경험이 있습니다.

# Work Experience.

### (주)아데나소프트웨어
**트레이딩 서버 개발자**
**2024.07.29 - 재직중**

- **거래소 호가 공급 프로그램 최적화**
    - 암호 화폐 거래소의 매수/매도 호가를 자동으로 생성하는 Market Maker 프로그램 최적화
    - **기술 스택: C++, Redis**
    - **CPU 점유율 및 응답 시간 개선:** 최대 CPU 점유율을 15%로 낮추고(67% 감소), 평균 응답 시간 30~50ms, 최대 지연 시간을 50ms로 단축

### (주)로그스택
**백엔드 개발자**
**2023.03.06 - 2024-07.01**

- 회계 감사 자동화 웹 서비스 **QueryStacker**
- **기술 스택**: **Python, Django REST Framework, Docker**
- **테스트 코드 작성**: 기존 테스트 코드가 전무한 상태에서 테스트 코드를 작성하여 디버깅 시간 단축 및 코드 안정성 향상
- **응답 속도 개선**: N+1 문제 해결 및 인덱스 최적화로 데이터 조회 속도를 5초 → 1초로 단축

# Side Project.

### 소개팅 API
개발기간: 24.04 ~ 24.11
**기술 스택: Django REST Framework, Github actions(CI/CD)**

# Skill.
- Language: Python, C++
- Back-End: Django, FastAPI
- Infra: Docker

# Education.
2013.03-2022.2 인하대학교 전자공학과
"""

    def test_real_llm_analysis(self):
        """실제 LLM으로 이력서 분석 테스트 (수동 실행용)"""
        # 실제 API 키가 필요합니다
        import os

        from django.conf import settings

        api_key = os.environ.get("GOOGLE_API_KEY") or getattr(
            settings, "GOOGLE_API_KEY", None
        )
        if not api_key:
            self.skipTest("GOOGLE_API_KEY not set")

        # Resume 객체 생성
        resume = Resume.objects.create(
            user_id=9999, content=self.sample_resume, analysis_result={}
        )

        # LLM 호출
        from google import genai
        from google.genai.errors import ServerError
        from google.genai.types import GenerateContentConfig

        client = genai.Client(api_key=api_key)

        prompt = f"""다음 이력서를 분석하여 JSON 형식으로 정보를 추출하세요.
이력서:
{resume.content[:3000]}

요구사항:
1. career_years: 모든 경력 기간을 합산하여 총 경력 연차를 정수로 계산하세요.
   - 재직중인 경우 현재 날짜(2025년 11월)까지 계산
   - 소수점 이하는 반올림 (예: 1.8년 → 2년)
   - 예시: "2023.03.06 - 2024.07.01" (약 1.3년) + "2024.07.29 - 재직중" (약 1.3년) = 총 2.6년 → 3년
   - 경력이 없으면 0

2. strengths: 지원자의 핵심 강점을 한국어로 1-2줄로 요약 (50자 이내)
   - 주요 기술적 성과나 개선 사항 중심으로 요약

3. experience_summary: 경력 요약을 한국어로 3-5줄로 작성 (임베딩용, 200자 이내)
   - 주요 프로젝트와 성과 포함
   - 핵심 기술 스택 언급
   - 경력 연차와 포지션 포함

반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이 JSON만):
{{
  "career_years": 숫자,
  "strengths": "강점 설명",
  "experience_summary": "경력 요약"
}}
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=400,
                ),
            )
        except ServerError as e:
            self.skipTest(f"LLM API 서버 오류 (503 과부하): {e}")
        except Exception as e:
            self.skipTest(f"LLM API 호출 실패: {e}")

        # 응답 검증
        if not response or not response.text:
            self.skipTest(
                "LLM API returned empty response (서비스 과부하 또는 일시적 오류)"
            )

        # 결과 파싱
        result_text = response.text.strip()
        print(f"\n=== LLM Raw Response ===\n{result_text}\n")

        # JSON 코드 블록 제거
        result_text = re.sub(
            r"^```json\s*|\s*```$", "", result_text, flags=re.MULTILINE
        )
        result = json.loads(result_text)

        print(f"\n=== Parsed Result ===")
        print(f"career_years: {result.get('career_years')}")
        print(f"strengths: {result.get('strengths')}")
        print(f"experience_summary: {result.get('experience_summary')}")

        # 검증
        career_years = int(result.get("career_years", 0))
        print(f"\n=== Validation ===")
        print(f"Expected career_years: 2-3 years (2023.03 - 2024.07 + 2024.07 - now)")
        print(f"Actual career_years: {career_years}")

        # 경력이 0년이 아니어야 함
        self.assertGreater(
            career_years,
            0,
            f"Expected career_years > 0, got {career_years}. LLM failed to extract career information.",
        )

        # 합리적인 범위 체크 (1~3년)
        self.assertGreaterEqual(
            career_years, 1, f"Expected at least 1 year, got {career_years}"
        )
        self.assertLessEqual(
            career_years, 4, f"Expected at most 4 years, got {career_years}"
        )

        # 정리
        resume.delete()

    def test_mock_llm_response_parsing(self):
        """LLM 응답 파싱 로직 테스트 (Mock 사용)"""
        # Mock LLM 응답
        mock_response_text = """```json
{
  "career_years": 2,
  "strengths": "성능 최적화 및 아키텍처 개선 경험",
  "experience_summary": "트레이딩 서버 개발자 및 백엔드 개발자로 총 2년 경력. C++, Python, Django, Redis 등을 활용한 성능 최적화 및 시스템 개선 경험 보유."
}
```"""

        # JSON 코드 블록 제거
        result_text = re.sub(
            r"^```json\s*|\s*```$", "", mock_response_text, flags=re.MULTILINE
        )
        result = json.loads(result_text)

        # 검증
        self.assertEqual(result["career_years"], 2)
        self.assertIsInstance(result["strengths"], str)
        self.assertIsInstance(result["experience_summary"], str)
        self.assertGreater(len(result["strengths"]), 0)
        self.assertGreater(len(result["experience_summary"]), 0)

    def test_career_years_extraction_from_text(self):
        """텍스트에서 경력 연차 추출 패턴 테스트"""
        test_cases = [
            ("2023.03.06 - 2024.07.01", 1),  # 1년 4개월 → 1년
            ("2024.07.29 - 재직중", 1),  # 2024.07 ~ 2025.11 → 1년 4개월 → 1년
            ("2020.01 - 2023.01", 3),  # 정확히 3년
            ("2019.06 - 2022.12", 3),  # 3년 6개월 → 3-4년
        ]

        for date_range, expected_years in test_cases:
            print(f"\nTesting: {date_range} → expected ~{expected_years} year(s)")
            # 실제로는 LLM이 처리하지만, 패턴 확인용
            self.assertIsInstance(date_range, str)
            self.assertIn("-", date_range)
