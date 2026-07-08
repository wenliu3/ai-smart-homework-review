"""Unit tests for app.core.utils."""
from datetime import datetime

import pytest

from app.core import utils


class TestNow:
    def test_returns_naive_datetime(self):
        result = utils.now()
        assert isinstance(result, datetime)
        assert result.tzinfo is None

    def test_close_to_current_utc(self):
        before = datetime.utcnow()
        result = utils.now()
        after = datetime.utcnow()
        assert before <= result <= after


class TestCamelToSnake:
    @pytest.mark.parametrize(
        "camel,snake",
        [
            ("camelCase", "camel_case"),
            ("PascalCase", "pascal_case"),
            ("HTTPResponse", "http_response"),
            ("getHTTPResponseCode", "get_http_response_code"),
            ("snake_case", "snake_case"),
            ("simple", "simple"),
            ("A", "a"),
            ("userID2", "user_id2"),
        ],
    )
    def test_conversion(self, camel, snake):
        assert utils.camel_to_snake(camel) == snake
