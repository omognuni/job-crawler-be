from __future__ import annotations

import uuid
from typing import Callable

from common.request_id import set_request_id
from django.http import HttpRequest, HttpResponse


class RequestIdMiddleware:
    """
    - 요청마다 request_id를 생성/전파하고
    - response에 X-Request-ID 헤더를 포함합니다.
    """

    header_name = "HTTP_X_REQUEST_ID"
    response_header = "X-Request-ID"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.META.get(self.header_name)
        request_id = str(incoming).strip() if incoming else str(uuid.uuid4())

        # request 객체에도 달아두고(디버깅), contextvar에도 저장(로깅 필터에서 사용)
        request.request_id = request_id  # type: ignore[attr-defined]
        set_request_id(request_id)

        response = self.get_response(request)
        response[self.response_header] = request_id
        return response
