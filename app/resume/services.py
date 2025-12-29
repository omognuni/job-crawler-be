"""
Resume Service

이력서 관리 및 분석 서비스
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone
from resume.dtos import ProcessResumeResultDTO, ResumeAnalysisResultDTO
from resume.embeddings import ResumeEmbeddingService
from resume.models import Resume
from skill.services import SkillExtractionService

logger = logging.getLogger(__name__)


class ResumeService:
    """
    이력서 서비스

    이력서 CRUD 및 분석 로직을 처리합니다.
    """

    @staticmethod
    def get_resume(user_id: int) -> Optional[Resume]:
        """
        이력서 조회 (User ID 기준)
        1:N 관계이므로 가장 최근에 수정된 이력서를 반환합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            Resume 객체 또는 None
        """
        try:
            return (
                Resume.objects.filter(user_id=user_id).order_by("-updated_at").first()
            )
        except Exception as e:
            logger.warning(f"Error fetching resume for user {user_id}: {e}")
            return None

    @staticmethod
    def get_resume_by_id(resume_id: int, user_id: int) -> Optional[Resume]:
        """
        이력서 조회 (Resume ID 및 User ID 기준)

        Args:
            resume_id: 이력서 ID
            user_id: 사용자 ID

        Returns:
            Resume 객체 또는 None
        """
        try:
            return Resume.objects.get(id=resume_id, user_id=user_id)
        except Resume.DoesNotExist:
            return None

    @staticmethod
    def get_all_resumes() -> List[Resume]:
        """
        모든 이력서 조회

        Returns:
            Resume 쿼리셋
        """
        return Resume.objects.all()

    @staticmethod
    def create_resume(data: Dict) -> Resume:
        """
        이력서 생성

        Args:
            data: 이력서 데이터 딕셔너리

        Returns:
            생성된 Resume 객체
        """
        with transaction.atomic():
            resume = Resume.objects.create(**data)
            logger.info(f"Created Resume {resume.id} for user {resume.user_id}")
            return resume

    @staticmethod
    def update_resume(resume_id: int, user_id: int, data: Dict) -> Optional[Resume]:
        """
        이력서 업데이트

        Args:
            resume_id: 이력서 ID
            user_id: 사용자 ID
            data: 업데이트할 데이터 딕셔너리

        Returns:
            업데이트된 Resume 객체 또는 None
        """
        resume = ResumeService.get_resume_by_id(resume_id, user_id)
        if not resume:
            return None

        with transaction.atomic():
            for key, value in data.items():
                setattr(resume, key, value)
            resume.save()
            resume.refresh_from_db()
            ResumeEmbeddingService.embed_resume(resume)
            logger.info(f"Updated Resume {resume_id} for user {user_id}")
            return resume

    @staticmethod
    def delete_resume(resume_id: int, user_id: int) -> bool:
        """
        이력서 삭제

        Args:
            resume_id: 이력서 ID
            user_id: 사용자 ID

        Returns:
            삭제 성공 여부
        """
        resume = ResumeService.get_resume_by_id(resume_id, user_id)
        if not resume:
            return False

        with transaction.atomic():
            resume.delete()
            logger.info(f"Deleted Resume {resume_id} for user {user_id}")
            return True

    @staticmethod
    def _analyze_resume_with_llm(content: str) -> ResumeAnalysisResultDTO:
        """
        LLM을 사용하여 이력서 분석

        Args:
            content: 이력서 내용

        Returns:
            ResumeAnalysisResultDTO: 분석 결과 (career_years, strengths, experience_summary)
        """
        # 스킬 추출 (LLM-Free)
        skills = SkillExtractionService.extract_skills(content)

        # LLM 호출
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Google API key not found - using fallback")
            return ResumeAnalysisResultDTO(
                skills=skills,
                career_years=0,
                strengths="API 키 미설정으로 분석 불가",
                experience_summary=f"보유 스킬: {', '.join(skills[:10])}",
            )

        try:
            from google import genai
            from google.genai.types import GenerateContentConfig

            client = genai.Client(api_key=api_key)

            # 긴 이력서를 처리하기 위해 청크 방식 사용
            # 처음 4000자와 마지막 1000자를 포함하여 주요 정보 손실 최소화
            if len(content) > 5000:
                # 긴 이력서: 앞부분 + 끝부분 결합
                content_preview = (
                    content[:4000] + "\n\n[... 중간 생략 ...]\n\n" + content[-1000:]
                )
            else:
                # 짧은 이력서: 전체 사용
                content_preview = content

            prompt = f"""다음 이력서를 분석하여 JSON 형식으로 정보를 추출하세요.
이력서:
{content_preview}

요구사항:
1. career_years: 모든 경력 기간을 합산하여 총 경력 연차를 정수로 계산하세요.
   - 재직중인 경우 현재 날짜(2025년 11월)까지 계산
   - 소수점 이하는 반올림 (예: 1.8년 → 2년)
   - 경력이 없으면 0

2. strengths: 지원자의 핵심 강점을 한국어로 1-2줄로 요약 (50자 이내)
   - 주요 기술적 성과나 개선 사항 중심으로 요약

3. experience_summary: 이 지원자가 지원할 수 있는 '가상의 채용 공고' 내용을 작성하세요. (임베딩 검색용, 500자 이내)
   - 지원자의 모든 기술 스택(Python, Django, C++, Redis 등)을 포괄하는 공고 스타일로 작성
   - 예: "Python 및 Django 기반의 대용량 트래픽 처리 백엔드 개발자...", "C++ 및 Redis를 활용한 고성능 트레이딩 시스템 개발자..."
   - 다양한 직무 가능성을 열어두고 풍부한 키워드를 포함하세요.

반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이 JSON만):
{{
  "career_years": 숫자,
  "strengths": "강점 설명",
  "experience_summary": "가상 채용 공고 내용"
}}
"""

            # LLM 호출 및 JSON 파싱 (재시도 로직 포함)
            max_retries = 3
            result = None

            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                        config=GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=400,
                        ),
                    )

                    # JSON 파싱
                    result_text = response.text.strip()
                    result_text = re.sub(
                        r"^```json\s*|\s*```$", "", result_text, flags=re.MULTILINE
                    )
                    result = json.loads(result_text)
                    break  # 파싱 성공 시 루프 종료

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {e}. 재시도합니다."
                        )
                        # 마지막 시도가 아니면 계속
                        continue
                    else:
                        # 최종 시도도 실패하면 예외 발생
                        logger.error(f"JSON 파싱 최종 실패: {e}")
                        raise
                except Exception as e:
                    # JSON 파싱이 아닌 다른 예외는 즉시 발생
                    logger.error(f"LLM 호출 실패: {e}")
                    raise

            # 파싱된 결과가 없으면 기본값 사용
            if not result:
                raise ValueError("LLM 응답 파싱 실패: 결과가 없습니다.")

            return ResumeAnalysisResultDTO(
                skills=skills,
                career_years=int(result.get("career_years", 0)),
                strengths=result.get("strengths", "분석 불가"),
                experience_summary=result.get(
                    "experience_summary",
                    f"경력 {result.get('career_years', 0)}년, {', '.join(skills[:5])} 경험",
                ),
            )

        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}", exc_info=True)
            # Fallback
            return ResumeAnalysisResultDTO(
                skills=skills,
                career_years=0,
                strengths=(
                    f"{', '.join(skills[:3])} 중심 경험"
                    if skills
                    else "이력서 분석 필요"
                ),
                experience_summary=f"보유 스킬: {', '.join(skills[:10])}",
            )

    @staticmethod
    def process_resume_sync(
        resume_id: int, force_reindex: bool = False
    ) -> ProcessResumeResultDTO:
        """
        이력서 처리 (동기 방식)

        분석, 임베딩 생성을 수행합니다.
        content_hash를 비교하여 변경이 없으면 LLM 분석을 건너뜁니다.
        Celery 작업에서 호출되거나, 테스트/관리 명령에서 직접 호출됩니다.

        Args:
            resume_id: 이력서 ID (기존 user_id에서 변경됨)
            force_reindex: 강제 재인덱싱 여부 (True일 경우 LLM 분석 건너뛰고 임베딩만 수행)

        Returns:
            ProcessResumeResultDTO: 처리 결과
        """
        try:
            # 1. Resume 조회
            try:
                resume = Resume.objects.get(id=resume_id)
            except Resume.DoesNotExist:
                error_msg = f"Resume {resume_id} not found"
                logger.error(error_msg)
                return ProcessResumeResultDTO(success=False, error=error_msg)

            user_id = resume.user_id

            # 2. content_hash 기반 변경 감지
            current_hash = resume.calculate_hash()
            existing_hash = resume.content_hash
            content_changed = current_hash != existing_hash

            # 3. LLM 분석 수행 (내용이 변경되었거나 분석 결과가 없거나 강제 재인덱싱인 경우)
            needs_analysis = (
                content_changed
                or not resume.analysis_result
                or not resume.experience_summary
            )

            if force_reindex:
                # 강제 재인덱싱: 분석은 건너뛰고 임베딩만 수행
                logger.info(
                    f"Force reindex requested for resume {resume_id}, skipping LLM analysis"
                )
                analysis = None
                needs_embedding = True
            elif needs_analysis:
                # LLM 분석 수행
                logger.info(
                    f"Content changed or missing analysis for resume {resume_id}, running LLM analysis"
                )
                analysis = ResumeService._analyze_resume_with_llm(resume.content)

                # Resume 업데이트
                resume.analysis_result = {
                    "skills": analysis.skills,
                    "career_years": analysis.career_years,
                    "strengths": analysis.strengths,
                }
                resume.experience_summary = analysis.experience_summary
                resume.analyzed_at = timezone.now()
                resume.save(
                    update_fields=[
                        "analysis_result",
                        "experience_summary",
                        "analyzed_at",
                        "content_hash",
                    ]
                )
                resume.refresh_from_db()

                logger.info(
                    f"Analyzed resume {resume_id}: {len(analysis.skills)} skills, "
                    f"{analysis.career_years} years"
                )
                needs_embedding = True
            else:
                # 내용이 변경되지 않았고 분석 결과가 이미 있음
                logger.info(
                    f"Content unchanged for resume {resume_id}, skipping LLM analysis"
                )
                analysis = None
                # experience_summary가 변경되었는지 확인하여 임베딩 필요 여부 결정
                # (현재는 단순화하여 항상 임베딩 수행, 향후 개선 가능)
                needs_embedding = True

            # 4. ChromaDB에 임베딩 (필요한 경우)
            if needs_embedding:
                ResumeEmbeddingService.embed_resume(resume)
                logger.info(f"Embedded resume {resume_id} to Vector DB")
            else:
                logger.info(f"Skipping embedding for resume {resume_id} (no changes)")

            # 5. 결과 반환
            if analysis:
                skills_count = len(analysis.skills)
                career_years = analysis.career_years
            elif resume.analysis_result:
                skills_count = len(resume.analysis_result.get("skills", []))
                career_years = resume.analysis_result.get("career_years", 0)
            else:
                skills_count = 0
                career_years = 0

            return ProcessResumeResultDTO(
                success=True,
                resume_id=resume_id,
                user_id=user_id,
                skills_count=skills_count,
                career_years=career_years,
            )

        except Exception as e:
            error_msg = f"Error processing resume {resume_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ProcessResumeResultDTO(success=False, error=error_msg)
