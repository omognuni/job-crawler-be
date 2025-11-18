import json
import os

import django
import requests
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from job.models import JobRecommendation, Resume
from job.recommender import get_recommendations


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
                # AI-Free 추천 엔진 사용
                recommendations_data = get_recommendations(
                    user_id=resume_obj.user_id, limit=20
                )

                # 추천 결과 검증
                if not recommendations_data:
                    warning_msg = f"⚠️ User {resume_obj.user_id}: 추천 결과가 없습니다."
                    print(f"\n[경고] {warning_msg}")
                    send_slack_message(warning_msg)
                    continue

                # JobRecommendation 모델에 저장
                saved_count = 0
                recommendations = []

                for rec_data in recommendations_data:
                    try:
                        # 기존 추천이 있으면 업데이트, 없으면 생성
                        recommendation, created = (
                            JobRecommendation.objects.update_or_create(
                                user_id=resume_obj.user_id,
                                job_posting_id=rec_data["posting_id"],
                                defaults={
                                    "match_score": rec_data["match_score"],
                                    "match_reason": rec_data["match_reason"],
                                },
                            )
                        )
                        saved_count += 1

                        # Slack 메시지용 데이터 구성
                        recommendations.append(
                            {
                                "company_name": rec_data["company_name"],
                                "position": rec_data["position"],
                                "url": rec_data["url"],
                                "match_score": rec_data["match_score"],
                                "match_reason": rec_data["match_reason"],
                            }
                        )
                    except Exception as e:
                        print(
                            f"[경고] 추천 저장 실패 (posting_id={rec_data.get('posting_id')}): {e}"
                        )
                        continue

                print(f"[정보] {saved_count}개의 추천을 DB에 저장했습니다.")

                # recommendations 추출
                recommendations = recommendations[:10]  # 최대 10개

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

                for rec in recommendations:
                    company_name = rec.get("company_name", "N/A")
                    position = rec.get("position", "N/A")
                    url = rec.get("url", "#")
                    match_score = rec.get("match_score", "N/A")
                    match_reason = rec.get("match_reason", "")

                    message_lines.append(
                        f"🏢 {company_name} - {position} (매칭: {match_score}점)\n   └ {match_reason}\n   <{url}|공고 보기>"
                    )

                message_text = "\n".join(message_lines)
                print(f"\n[성공] {len(recommendations)}개의 추천 완료")
                send_slack_message(message_text)

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
