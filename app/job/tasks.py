"""
Celery 태스크: 채용 공고 및 이력서 처리
"""

from celery import shared_task
from common.graph_db import graph_db_client
from common.vector_db import vector_db_client
from django.utils import timezone
from skill.services import extract_skills, extract_skills_from_job_posting

from .models import JobPosting, Resume


@shared_task(bind=True, max_retries=3)
def process_job_posting(self, posting_id: int):
    """
    채용 공고를 처리하는 Celery 태스크

    1. posting_id로 JobPosting 조회
    2. skill_extractor로 스킬 추출 → skills_required, skills_preferred 업데이트
    3. 임베딩 벡터 생성 (position + main_tasks + requirements)
    4. ChromaDB 'job_postings' 컬렉션에 upsert
    5. Neo4j에 (JobPosting)-[:REQUIRES_SKILL]->(Skill) 관계 생성

    Args:
        posting_id: JobPosting의 ID

    Returns:
        dict: 처리 결과
    """
    try:
        # 1. JobPosting 조회
        try:
            job_posting = JobPosting.objects.get(posting_id=posting_id)
        except JobPosting.DoesNotExist:
            error_msg = f"JobPosting {posting_id} not found"
            print(f"[ERROR] {error_msg}")
            return {"success": False, "error": error_msg}

        # 2. 스킬 추출
        skills_required, skills_preferred = extract_skills_from_job_posting(
            requirements=job_posting.requirements,
            preferred_points=job_posting.preferred_points,
            main_tasks=job_posting.main_tasks,
        )

        # skills_required와 skills_preferred 업데이트 (변경이 있을 경우에만)
        if (
            job_posting.skills_required != skills_required
            or job_posting.skills_preferred != skills_preferred
        ):
            job_posting.skills_required = skills_required
            job_posting.skills_preferred = skills_preferred
            job_posting.save(update_fields=["skills_required", "skills_preferred"])
            print(
                f"[INFO] Updated skills for posting {posting_id}: "
                f"Required={len(skills_required)}, Preferred='{skills_preferred[:50]}...'"
            )

        # 3. 임베딩 텍스트 생성 (노이즈 제거)
        # 회사 소개, 위치, 복지 등을 제외하고 핵심 정보만 임베딩
        embedding_text = f"""
Position: {job_posting.position or 'N/A'}
Main Tasks: {job_posting.main_tasks or 'N/A'}
Requirements: {job_posting.requirements or 'N/A'}
Preferred Points: {job_posting.preferred_points or 'N/A'}
        """.strip()

        # 4. ChromaDB에 upsert (텍스트가 충분히 긴 경우에만)
        if len(embedding_text) > 10:  # 최소 길이 체크
            try:
                collection = vector_db_client.get_or_create_collection("job_postings")
                vector_db_client.upsert_documents(
                    collection=collection,
                    documents=[embedding_text],
                    metadatas=[
                        {
                            "company_name": job_posting.company_name or "",
                            "location": job_posting.location or "",
                            "employment_type": job_posting.employment_type or "",
                            "career_min": job_posting.career_min,
                            "career_max": job_posting.career_max,
                        }
                    ],
                    ids=[str(posting_id)],
                )
                print(f"[INFO] Embedded job posting {posting_id} to Vector DB")
            except Exception as e:
                print(
                    f"[WARNING] Failed to embed posting {posting_id} to Vector DB: {str(e)}"
                )
                # ChromaDB 실패는 치명적이지 않으므로 계속 진행
        else:
            print(
                f"[WARNING] Skipping embedding for posting {posting_id}: text too short"
            )

        # 5. Neo4j에 관계 생성 (필수 스킬만)
        if skills_required:
            graph_db_client.add_job_posting(
                posting_id=posting_id,
                position=job_posting.position,
                company_name=job_posting.company_name,
                skills=skills_required,
            )
            print(
                f"[INFO] Saved job posting {posting_id} to Graph DB with {len(skills_required)} required skills"
            )

        return {
            "success": True,
            "posting_id": posting_id,
            "skills_required": len(skills_required),
            "skills_preferred_text": skills_preferred[:50] if skills_preferred else "",
        }

    except Exception as e:
        error_msg = f"Error processing job posting {posting_id}: {str(e)}"
        print(f"[ERROR] {error_msg}")

        # 재시도
        try:
            raise self.retry(exc=e, countdown=60)  # 60초 후 재시도
        except self.MaxRetriesExceededError:
            print(f"[ERROR] Max retries exceeded for posting {posting_id}")
            return {"success": False, "error": error_msg}


@shared_task(bind=True, max_retries=3)
def process_resume(self, user_id: int):
    """
    이력서를 처리하는 Celery 태스크

    1. user_id로 Resume 조회
    2. needs_analysis() 체크 (해시 비교)
    3. LLM 호출 (1회) → analysis_result + experience_summary 동시 추출
    4. Resume 업데이트 (update_fields 사용)
    5. experience_summary 임베딩 생성
    6. ChromaDB 'resumes' 컬렉션에 upsert

    Args:
        user_id: User ID

    Returns:
        dict: 처리 결과
    """
    import json
    import os
    import re

    try:
        # 1. Resume 조회
        try:
            resume = Resume.objects.get(user_id=user_id)
        except Resume.DoesNotExist:
            error_msg = f"Resume for user {user_id} not found"
            print(f"[ERROR] {error_msg}")
            return {"success": False, "error": error_msg}

        # 2. 분석 필요 여부 체크
        if not resume.needs_analysis():
            print(f"[INFO] Resume {user_id} does not need re-analysis (hash unchanged)")
            return {
                "success": True,
                "user_id": user_id,
                "skipped": True,
                "reason": "No changes detected",
            }

        # 3. 스킬 추출 (LLM-Free)
        # extract_skills는 이미 상단에서 import됨
        skills = extract_skills(resume.content)

        # 4. LLM 호출 (1회) - 경력, 강점, 경력 요약 동시 추출
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            # API 키가 없으면 Fallback
            analysis_result = {
                "skills": skills,
                "career_years": 0,
                "strengths": "API 키 미설정으로 분석 불가",
            }
            experience_summary = f"보유 스킬: {', '.join(skills[:10])}"
            print(f"[WARN] No Google API key - using fallback for resume {user_id}")
        else:
            try:
                from google import genai
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
                # JSON 코드 블록 제거
                result_text = re.sub(
                    r"^```json\s*|\s*```$", "", result_text, flags=re.MULTILINE
                )
                result = json.loads(result_text)

                analysis_result = {
                    "skills": skills,
                    "career_years": int(result.get("career_years", 0)),
                    "strengths": result.get("strengths", "분석 불가"),
                }
                experience_summary = result.get(
                    "experience_summary",
                    f"경력 {analysis_result['career_years']}년, {', '.join(skills[:5])} 경험",
                )

                print(f"[INFO] LLM analysis complete for resume {user_id}")

            except Exception as e:
                print(f"[WARN] LLM analysis failed for resume {user_id}: {e}")
                # Fallback
                analysis_result = {
                    "skills": skills,
                    "career_years": 0,
                    "strengths": (
                        f"{', '.join(skills[:3])} 중심 경험"
                        if skills
                        else "이력서 분석 필요"
                    ),
                }
                experience_summary = f"보유 스킬: {', '.join(skills[:10])}"

        # 5. Resume 업데이트
        resume.analysis_result = analysis_result
        resume.experience_summary = experience_summary
        resume.analyzed_at = timezone.now()
        resume.save(
            update_fields=[
                "analysis_result",
                "experience_summary",
                "analyzed_at",
                "content_hash",
            ]
        )

        print(
            f"[INFO] Analyzed resume {user_id}: {len(skills)} skills, "
            f"{analysis_result.get('career_years', 0)} years"
        )

        # 6. ChromaDB에 임베딩
        if experience_summary and len(experience_summary) > 10:
            try:
                collection = vector_db_client.get_or_create_collection("resumes")
                vector_db_client.upsert_documents(
                    collection=collection,
                    documents=[experience_summary],
                    metadatas=[
                        {
                            "career_years": analysis_result.get("career_years", 0),
                            "skills_count": len(skills),
                        }
                    ],
                    ids=[str(user_id)],
                )
                print(f"[INFO] Embedded resume {user_id} to Vector DB")
            except Exception as e:
                print(
                    f"[WARNING] Failed to embed resume {user_id} to Vector DB: {str(e)}"
                )
                # ChromaDB 실패는 치명적이지 않으므로 계속 진행
        else:
            print(
                f"[WARNING] Skipping embedding for resume {user_id}: summary too short or empty"
            )

        return {
            "success": True,
            "user_id": user_id,
            "skills_count": len(skills),
            "career_years": analysis_result.get("career_years", 0),
        }

    except Exception as e:
        error_msg = f"Error processing resume {user_id}: {str(e)}"
        print(f"[ERROR] {error_msg}")

        # 재시도
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            print(f"[ERROR] Max retries exceeded for resume {user_id}")
            return {"success": False, "error": error_msg}
