import pytest
import json
from unittest.mock import patch, MagicMock
from django.utils import timezone
from django.conf import settings

from agent.models import JobPosting, Resume, JobRecommendation
from agent.tasks import JobHunterCrew

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_env(monkeypatch):
    """API 키에 대한 환경 변수를 모킹합니다."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")


@pytest.fixture
def crew_instance(mock_env):
    """테스트에 사용할 JobHunterCrew 인스턴스를 생성합니다."""
    return JobHunterCrew(user_id=1)


def test_api_key_validation(monkeypatch):
    """API 키가 없을 때 ValueError가 발생하는지 테스트합니다."""
    
    # 두 키가 모두 있을 때 (성공)
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
    try:
        JobHunterCrew(user_id=1)
    except ValueError:
        pytest.fail("API 키가 모두 있어도 ValueError 발생")

    # OPENAI_API_KEY가 없을 때 (실패)
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        JobHunterCrew(user_id=1)

    # GOOGLE_API_KEY가 없을 때 (실패)
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.delenv("GOOGLE_API_KEY")
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        JobHunterCrew(user_id=1)


def test_fetch_filtered_job_postings_tool(crew_instance):
    """fetch_job_postings_tool이 DB에서 공고를 올바르게 가져오는지 테스트합니다."""
    # 테스트 데이터 생성
    JobPosting.objects.create(
        posting_id=1,
        company_name="Test Co",
        position="Backend Developer",
        career_min=0,
        career_max=10,
        main_tasks="Test main tasks",
        requirements="Test requirements",
        preferred_points="Test preferred points",
        location="Test location",
        district="Test district",
        employment_type="Test employment type",
    )
    
    result_json = crew_instance.fetch_filtered_job_postings_tool(career_years=3, skills=["Python", "Django"])
    result_data = json.loads(result_json)
    
    assert isinstance(result_data, list)
    assert len(result_data) == 1
    assert result_data[0]['posting_id'] == 1
    assert result_data[0]['company_name'] == "Test Co"


def test_get_resume_tool_cached(crew_instance, mocker):
    """get_resume_tool이 캐시된 분석 결과를 반환하는지 테스트합니다."""
    analysis_data = {"skills": ["Python", "Django"]}
    
    # Resume.needs_analysis()가 False를 반환하도록 모킹
    mocker.patch.object(Resume, 'needs_analysis', return_value=False)
    
    Resume.objects.create(
        user_id=1,
        content="Test resume content",
        analysis_result=analysis_data,
        analyzed_at=timezone.now()
    )
    
    result_json = crew_instance.get_resume_tool(user_id=1)
    result_data = json.loads(result_json)
    
    assert result_data['status'] == 'cached'
    assert result_data['user_id'] == 1
    assert result_data['analysis_result'] == analysis_data


def test_get_resume_tool_needs_analysis(crew_instance, mocker):
    """get_resume_tool이 분석 필요 상태를 반환하는지 테스트합니다."""
    
    # Resume.needs_analysis()가 True를 반환하도록 모킹
    mocker.patch.object(Resume, 'needs_analysis', return_value=True)
    
    Resume.objects.create(
        user_id=1,
        content="New resume content",
        analysis_result=None,
    )
    
    result_json = crew_instance.get_resume_tool(user_id=1)
    result_data = json.loads(result_json)
    
    assert result_data['status'] == 'needs_analysis'
    assert result_data['user_id'] == 1
    assert result_data['content'] == "New resume content"


def test_get_resume_tool_not_found(crew_instance):
    """get_resume_tool이 이력서를 찾지 못했을 때 오류를 반환하는지 테스트합니다."""
    result_json = crew_instance.get_resume_tool(user_id=999) # 존재하지 않는 ID
    result_data = json.loads(result_json)
    
    assert result_data['status'] == 'error'
    assert '찾을 수 없습니다' in result_data['message']


def test_analyze_resume_tool(crew_instance):
    """analyze_resume_tool이 분석 결과를 DB에 저장하는지 테스트합니다."""
    resume = Resume.objects.create(
        user_id=1,
        content="Test resume content"
    )
    
    analysis_data = {
        "skills": ["Python", "C++", "Django"],
        "experiences": "5 years backend dev",
        "strengths": "Fast learner",
        "career_years": 5,
        "preferred_areas": ["Backend", "DevOps"]
    }
    
    result_json = crew_instance.analyze_resume_tool(user_id=1, analysis_result=analysis_data)
    result_data = json.loads(result_json)
    
    # DB에서 데이터 새로고침
    resume.refresh_from_db()
    
    assert result_data['status'] == 'success'
    assert resume.analysis_result == analysis_data
    assert resume.analyzed_at is not None


def test_save_recommendations_tool(crew_instance):
    """save_recommendations_tool이 추천 목록을 DB에 저장하는지 테스트합니다."""
    # 의존성 데이터 생성
    jp1 = JobPosting.objects.create(posting_id=1, company_name="Test Co 1", position="Dev 1", career_min=0, career_max=10)
    jp2 = JobPosting.objects.create(posting_id=2, company_name="Test Co 2", position="Dev 2", career_min=0, career_max=10)
    
    recommendations = [
        {"posting_id": 1, "rank": 1, "match_score": 95, "match_reason": "Good fit"},
        {"posting_id": 2, "rank": 2, "match_score": 90, "match_reason": "Okay fit"},
        {"posting_id": 3, "rank": 3, "match_score": 88, "match_reason": "No data"}, # 존재하지 않는 공고
    ]
    
    result_json = crew_instance.save_recommendations_tool(user_id=1, recommendations=recommendations)
    result_data = json.loads(result_json)
    
    assert result_data['status'] == 'success'
    assert result_data['saved_count'] == 2 # 2개만 저장되어야 함 (jp_non_existent 제외)
    
    saved_recs = JobRecommendation.objects.filter(user_id=1).order_by('rank')
    assert saved_recs.count() == 2
    assert saved_recs[0].job_posting == jp1
    assert saved_recs[0].rank == 1
    assert saved_recs[1].job_posting == jp2
    assert saved_recs[1].match_score == 90


def test_save_recommendations_tool_top_10_limit(crew_instance):
    """save_recommendations_tool이 최대 10개만 저장하는지 테스트합니다."""
    # 12개의 공고와 추천 목록 생성
    mock_recs = []
    for i in range(1, 13):
        posting_id = i
        JobPosting.objects.create(posting_id=posting_id, company_name=f"Test Co {i}", position=f"Dev {i}", career_min=0, career_max=10)
        mock_recs.append({
            "posting_id": posting_id,
            "rank": i,
            "match_score": 100 - i,
            "match_reason": "Test"
        })
        
    crew_instance.save_recommendations_tool(user_id=1, recommendations=mock_recs)
    
    # DB에는 10개만 저장되어야 함
    assert JobRecommendation.objects.count() == 10
    assert JobRecommendation.objects.filter(user_id=1, rank=10).exists()
    assert not JobRecommendation.objects.filter(user_id=1, rank=11).exists()


@patch('crewai.Crew.kickoff')
def test_crew_kickoff_mocked(MockKickoff, crew_instance):
    """
    Crew가 올바르게 조립되고 kickoff이 (모킹된 상태로) 호출되는지 테스트합니다.
    """

    mock_kickoff_result = {
        "status": "success", 
        "final_output": "Some mocked result"
    }
    MockKickoff.return_value = mock_kickoff_result

    crew_obj = crew_instance.job_hunter_crew() 

    result = crew_obj.kickoff()
    MockKickoff.assert_called_once()
    
    assert result == mock_kickoff_result
    assert crew_obj is not None
    assert len(crew_obj.agents) == 3  # @agent 3개 등록 확인
    assert len(crew_obj.tasks) == 3  # @task 3개 등록 확인
    
    # (선택적) 에이전트 역할 스팟 체크
    agent_roles = [agent.role for agent in crew_obj.agents]
    assert "Resume Inspector" in agent_roles
    assert "Job Posting Inspector" in agent_roles
    assert "Job Hunter" in agent_roles