import os
import django
import json
import pathlib  # 1. pathlib 임포트
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from agent.models import Resume, JobRecommendation
from agent.tasks import JobHunterCrew

# 테스트할 사용자 ID
TEST_USER_ID = 1

# 2. 이력서 파일 경로 변수 정의 (스크립트와 같은 위치)
BASE_DIR = pathlib.Path(__file__).resolve().parent
RESUME_FILE_PATH = BASE_DIR / "my_resume.md"


def setup_test_data(user_id: int):
    """
    테스트를 위한 초기 데이터를 설정합니다.
    기존 데이터를 삭제하고 새로운 테스트용 이력서와 공고를 생성합니다.
    """
    print(f"--- {user_id}번 사용자의 테스트 데이터 설정 시작 ---")
    Resume.objects.filter(user_id=user_id).delete()
    JobRecommendation.objects.filter(user_id=user_id).delete()
    
    print("기존 데이터 정리 완료.")

    # 3. .md 파일에서 이력서 내용 읽기
    try:
        resume_content = RESUME_FILE_PATH.read_text(encoding='utf-8')
        print(f"'{RESUME_FILE_PATH.name}' 파일 읽기 성공.")
    except FileNotFoundError:
        print(f"[오류] 이력서 파일을 찾을 수 없습니다: {RESUME_FILE_PATH}")
        print("스크립트를 종료합니다.")
        return False  # 데이터 설정 실패

    # 4. 테스트 이력서 생성 (파일에서 읽은 내용 사용)
    Resume.objects.create(
        user_id=user_id,
        content=resume_content  # <--- 수정된 부분
    )
    print("테스트 이력서 생성 완료.")
    print("--- 테스트 데이터 설정 완료 ---")
    return True # 데이터 설정 성공


def main():
    """
    테스트 스크립트의 메인 실행 함수
    """
    
    # 1. 테스트 데이터 준비
    if not setup_test_data(TEST_USER_ID):
        return  # 이력서 파일이 없으면 중단

    print(f"\n--- {TEST_USER_ID}번 사용자 JobHunterCrew 실제 실행 시작 ---")
    
    try:
        # ( ... 이하 main 함수 내용은 이전과 동일 ... )
        crew_runner = JobHunterCrew(user_id=TEST_USER_ID)
        crew = crew_runner.job_hunter_crew()
        crew.verbose = 2 
        
        print("Crew.kickoff() 호출... (LLM API 호출로 인해 시간이 걸릴 수 있습니다)")
        
        start_time = datetime.now()
        result = crew.kickoff()
        end_time = datetime.now()
        
        print("\n--- Crew 실행 완료 ---")
        print(f"총 실행 시간: {end_time - start_time}")
        
        print("\n[최종 결과 (Raw)]:")
        if isinstance(result, dict):
             print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result)

        print("\n--- 데이터베이스 저장 결과 검증 ---")
        saved_recs = JobRecommendation.objects.filter(user_id=TEST_USER_ID).order_by('rank')
        
        if not saved_recs.exists():
            print(f"[실패] {TEST_USER_ID}번 사용자의 추천 공고가 DB에 저장되지 않았습니다.")
        else:
            print(f"[성공] 총 {saved_recs.count()}건의 추천 공고가 DB에 저장되었습니다.")
            for rec in saved_recs:
                print(f"  - Rank {rec.rank}: {rec.job_posting.company_name} - {rec.job_posting.position} (Score: {rec.match_score})")
                print(f"    Reason: {rec.match_reason[:50]}...")

    except Exception as e:
        print(f"\n[오류] 스크립트 실행 중 예외가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n--- 테스트 스크립트 종료 ---")

if __name__ == "__main__":
    main()