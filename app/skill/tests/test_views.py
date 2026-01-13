import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestSkillViews:
    def setup_method(self):
        self.client = APIClient()

    def test_get_skill_options_public(self):
        response = self.client.get("/api/v1/skills/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert "Python" in response.data
