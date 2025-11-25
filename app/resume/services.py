"""
Resume Service

이력서 관리 및 분석 서비스
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional

from common.vector_db import vector_db_client
from django.db import transaction
from django.utils import timezone
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
    def analyze_resume_with_llm(content: str) -> Dict:
        """
        LLM을 사용하여 이력서 분석

        Args:
            content: 이력서 내용

        Returns:
            분석 결과 딕셔너리 (career_years, strengths, experience_summary)
        """
        # 스킬 추출 (LLM-Free)
        skills = SkillExtractionService.extract_skills(content)

        # LLM 호출
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Google API key not found - using fallback")
            return {
                "skills": skills,
                "career_years": 0,
                "strengths": "API 키 미설정으로 분석 불가",
                "experience_summary": f"보유 스킬: {', '.join(skills[:10])}",
            }

        try:
            from google import genai
            from google.genai.types import GenerateContentConfig

            client = genai.Client(api_key=api_key)

            prompt = f"""다음 이력서를 분석하여 JSON 형식으로 정보를 추출하세요.
이력서:
{content[:3000]}

요구사항:
1. career_years: 모든 경력 기간을 합산하여 총 경력 연차를 정수로 계산하세요.
   - 재직중인 경우 현재 날짜(2025년 11월)까지 계산
   - 소수점 이하는 반올림 (예: 1.8년 → 2년)
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

            return {
                "skills": skills,
                "career_years": int(result.get("career_years", 0)),
                "strengths": result.get("strengths", "분석 불가"),
                "experience_summary": result.get(
                    "experience_summary",
                    f"경력 {result.get('career_years', 0)}년, {', '.join(skills[:5])} 경험",
                ),
            }

        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}", exc_info=True)
            # Fallback
            return {
                "skills": skills,
                "career_years": 0,
                "strengths": (
                    f"{', '.join(skills[:3])} 중심 경험"
                    if skills
                    else "이력서 분석 필요"
                ),
                "experience_summary": f"보유 스킬: {', '.join(skills[:10])}",
            }

    @staticmethod
    def process_resume_sync(resume_id: int, reindex: bool = False) -> Dict:
        """
        이력서 처리 (동기 방식)

        분석, 임베딩 생성을 수행합니다.
        Celery 작업에서 호출되거나, 테스트/관리 명령에서 직접 호출됩니다.

        Args:
            resume_id: 이력서 ID (기존 user_id에서 변경됨)
            reindex: 강제 재인덱싱 여부 (True일 경우 LLM 분석 건너뛰고 임베딩만 수행)

        Returns:
            처리 결과 딕셔너리
        """
        try:
            # 1. Resume 조회
            try:
                resume = Resume.objects.get(id=resume_id)
            except Resume.DoesNotExist:
                error_msg = f"Resume {resume_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            user_id = resume.user_id

            # 2. 분석 필요 여부 체크
            # reindex가 True이면 분석 필요 여부와 상관없이 진행하되, LLM 분석은 건너뜀
            if not reindex and not resume.needs_analysis():
                logger.info(
                    f"Resume {resume_id} does not need re-analysis (hash unchanged)"
                )
                return {
                    "success": True,
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "skipped": True,
                    "reason": "No changes detected",
                }

            # 3. LLM 분석 (reindex가 아니고, 분석이 필요한 경우에만 수행)
            if not reindex:
                analysis = ResumeService.analyze_resume_with_llm(resume.content)

                # 4. Resume 업데이트
                resume.analysis_result = {
                    "skills": analysis["skills"],
                    "career_years": analysis["career_years"],
                    "strengths": analysis["strengths"],
                }
                resume.experience_summary = analysis["experience_summary"]
                resume.analyzed_at = timezone.now()
                resume.save(
                    update_fields=[
                        "analysis_result",
                        "experience_summary",
                        "analyzed_at",
                        "content_hash",
                    ]
                )

                logger.info(
                    f"Analyzed resume {resume_id}: {len(analysis['skills'])} skills, "
                    f"{analysis['career_years']} years"
                )
            else:
                # Reindex 모드: 기존 분석 결과 사용
                if not resume.analysis_result or not resume.experience_summary:
                    logger.warning(
                        f"Resume {resume_id} has no analysis result, skipping reindex optimization and running full analysis"
                    )
                    # 분석 결과가 없으면 reindex라도 분석 수행
                    return ResumeService.process_resume_sync(resume_id, reindex=False)

                analysis = {
                    "skills": resume.analysis_result.get("skills", []),
                    "career_years": resume.analysis_result.get("career_years", 0),
                    "experience_summary": resume.experience_summary,
                }
                logger.info(f"Re-indexing resume {resume_id} (skipping LLM analysis)")

            # 5. ChromaDB에 임베딩
            if (
                analysis["experience_summary"]
                and len(analysis["experience_summary"]) > 10
            ):
                try:
                    collection = vector_db_client.get_or_create_collection("resumes")
                    vector_db_client.upsert_documents(
                        collection=collection,
                        documents=[analysis["experience_summary"]],
                        metadatas=[
                            {
                                "career_years": analysis["career_years"],
                                "skills_count": len(analysis["skills"]),
                                "user_id": user_id,  # 메타데이터에 user_id 추가
                            }
                        ],
                        ids=[str(resume_id)],  # Vector DB ID는 resume_id 사용
                    )
                    logger.info(f"Embedded resume {resume_id} to Vector DB")
                except Exception as e:
                    logger.warning(
                        f"Failed to embed resume {resume_id} to Vector DB: {str(e)}"
                    )

            return {
                "success": True,
                "resume_id": resume_id,
                "user_id": user_id,
                "skills_count": len(analysis["skills"]),
                "career_years": analysis["career_years"],
            }

        except Exception as e:
            error_msg = f"Error processing resume {resume_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}
