import pytest
from job.models import JobPosting
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestJobCompanyOptionsView:
    def setup_method(self):
        self.client = APIClient()

    def test_company_options_public_typeahead(self):
        JobPosting.objects.create(
            posting_id=1000,
            url="https://example.com/job/1000",
            company_name="Company Alpha",
            position="Dev",
        )
        JobPosting.objects.create(
            posting_id=1001,
            url="https://example.com/job/1001",
            company_name="Company Beta",
            position="Dev",
        )

        response = self.client.get("/api/v1/jobs/companies/?q=Alpha&limit=5")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == ["Company Alpha"]

    def test_company_options_invalid_limit_returns_400(self):
        response = self.client.get("/api/v1/jobs/companies/?limit=0")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "details" in response.data
