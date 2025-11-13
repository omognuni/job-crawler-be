import json
import os

import django
import requests
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from agent.crew import JobHunterCrew
from crewai import CrewOutput
from job.models import Resume


def main():
    try:
        if not settings.SLACK_WEBHOOK_URL:
            raise ValueError("SLACK_WEBHOOK_URL is not set")

        resume_objs = Resume.objects.all()
        for resume_obj in resume_objs:
            crew = JobHunterCrew(user_id=resume_obj.user_id)
            result = crew.run()

            try:
                data = result.json_dict
                recommendations = data.get("recommendations", [])

                message_lines = [
                    f"✨ {len(recommendations)}개의 채용 공고 추천이 완료되었습니다 ✨\n"
                ]

                for rec in recommendations:
                    company_name = rec.get("company_name", "N/A")
                    position = rec.get("position", "N/A")
                    url = rec.get("url", "#")
                    message_lines.append(
                        f"🏢 {company_name} - {position}\n<{url}|공고 보기>"
                    )

                message_text = "\n".join(message_lines)
                payload = {"text": message_text}
                response = requests.post(
                    settings.SLACK_WEBHOOK_URL,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
            except (json.JSONDecodeError, AttributeError) as e:
                payload = {"text": f"오류가 발생했습니다: {e}"}
                response = requests.post(
                    settings.SLACK_WEBHOOK_URL,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )

    except Exception as e:
        print(f"\n[오류] 스크립트 실행 중 예외가 발생했습니다: {e}")
        import traceback

        payload = {"text": f"오류가 발생했습니다: {e}"}
        response = requests.post(
            settings.SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        traceback.print_exc()


if __name__ == "__main__":
    main()
