import os
import django
import json
import requests
from django.conf import settings
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from agent.models import Resume, JobRecommendation
from agent.tasks import JobHunterCrew


def main():
    try:
        resume_objs = Resume.objects.all()
        for resume_obj in resume_objs:
            crew_runner = JobHunterCrew(user_id=resume_obj.user_id)
            crew = crew_runner.job_hunter_crew()
            crew.verbose = 2
            result = crew.kickoff()

            message_text = f"""
            ✨ Job Hunter 추천 완료 ✨

            DB 저장 결과가 도착했습니다:
            ```
            {result}
            ```
            """

            payload = {"text": message_text}
            response = requests.post(
                settings.SLACK_WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

    except Exception as e:
        print(f"\n[오류] 스크립트 실행 중 예외가 발생했습니다: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
