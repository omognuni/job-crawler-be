from __future__ import annotations

import logging

from common.request_id import get_request_id


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # formatter에서 %(request_id)s 를 안전하게 쓰도록 보장
        record.request_id = get_request_id()  # type: ignore[attr-defined]
        return True
