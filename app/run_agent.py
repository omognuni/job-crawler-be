import json
import os

import django
import requests
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from agent.crew import JobHunterCrew
from job.models import JobRecommendation, Resume


def send_slack_message(message_text: str) -> bool:
    """Slack 메시지 전송 헬퍼 함수"""
    try:
        if not settings.SLACK_WEBHOOK_URL:
            print(
                f"[경고] SLACK_WEBHOOK_URL이 설정되지 않아 메시지를 전송하지 않습니다: {message_text}"
            )
            return False

        payload = {"text": message_text}
        response = requests.post(
            settings.SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        print(f"[성공] Slack 메시지 전송 완료")
        return True
    except Exception as e:
        print(f"[오류] Slack 메시지 전송 실패: {e}")
        return False


def main():
    try:
        if not settings.SLACK_WEBHOOK_URL:
            print("[경고] SLACK_WEBHOOK_URL이 설정되지 않았습니다.")

        resume_objs = Resume.objects.all()

        if not resume_objs.exists():
            message = "⚠️ 분석할 이력서가 없습니다."
            print(f"\n{message}")
            send_slack_message(message)
            return

        for resume_obj in resume_objs:
            print(f"\n{'='*60}")
            print(f"[시작] User {resume_obj.user_id}의 채용 공고 추천 시작")
            print(f"{'='*60}")

            try:
                crew = JobHunterCrew(user_id=resume_obj.user_id)
                result = crew.run()

                # result 검증
                if result is None:
                    error_msg = (
                        f"❌ User {resume_obj.user_id}: Agent 실행 결과가 None입니다."
                    )
                    print(f"\n[오류] {error_msg}")
                    send_slack_message(error_msg)
                    continue

                # json_dict 추출 및 검증
                data = None
                if hasattr(result, "json_dict"):
                    data = result.json_dict
                elif hasattr(result, "raw"):
                    # Fallback: raw 출력에서 JSON 파싱 시도
                    try:
                        data = json.loads(result.raw)
                    except (json.JSONDecodeError, TypeError):
                        pass

                if data is None or not isinstance(data, dict):
                    recent_recs = (
                        JobRecommendation.objects.filter(user_id=resume_obj.user_id)
                        .select_related("job_posting")
                        .order_by("-created_at")[:10]
                    )

                    data = {
                        "recommendations": [
                            {
                                "company_name": rec.job_posting.company_name,
                                "position": rec.job_posting.position,
                                "url": rec.job_posting.url,
                                "match_score": (
                                    int(rec.match_score) if rec.match_score else 0
                                ),
                                "match_reason": rec.match_reason or "이전 추천",
                            }
                            for rec in recent_recs
                        ]
                    }

                # recommendations 추출
                recommendations = data.get("recommendations", [])

                if not recommendations:
                    warning_msg = (
                        f"⚠️ User {resume_obj.user_id}: 추천할 채용 공고가 없습니다."
                    )
                    print(f"\n[경고] {warning_msg}")
                    send_slack_message(warning_msg)
                    continue

                # Slack 메시지 생성
                message_lines = [
                    f"✨ User {resume_obj.user_id}님을 위한 {len(recommendations)}개의 채용 공고 추천 ✨\n"
                ]

                for rec in recommendations[:10]:  # 최대 10개만 전송
                    company_name = rec.get("company_name", "N/A")
                    position = rec.get("position", "N/A")
                    url = rec.get("url", "#")
                    match_score = rec.get("match_score", "N/A")

                    message_lines.append(
                        f"🏢 {company_name} - {position} (매칭: {match_score}%)\n<{url}|공고 보기>"
                    )

                message_text = "\n".join(message_lines)
                print(f"\n[성공] {len(recommendations)}개의 추천 완료")
                send_slack_message(message_text)

            except ValueError as e:
                error_msg = f"❌ User {resume_obj.user_id}: 설정 오류 - {e}"
                print(f"\n[오류] {error_msg}")
                send_slack_message(error_msg)

            except Exception as e:
                error_msg = f"❌ User {resume_obj.user_id}: 예상치 못한 오류 - {type(e).__name__}: {e}"
                print(f"\n[오류] {error_msg}")
                import traceback

                traceback.print_exc()
                send_slack_message(error_msg)

    except Exception as e:
        error_msg = f"❌ 스크립트 실행 중 치명적 오류 발생: {type(e).__name__}: {e}"
        print(f"\n[오류] {error_msg}")
        import traceback

        traceback.print_exc()
        send_slack_message(error_msg)


if __name__ == "__main__":
    main()
