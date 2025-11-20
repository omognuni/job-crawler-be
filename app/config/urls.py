"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_http_methods
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


@require_http_methods(["GET"])
def health_check(request):
    """헬스체크 엔드포인트"""
    return JsonResponse({"status": "healthy", "message": "Service is running"})


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # API v1 Endpoints
    path("api/v1/jobs/", include("job.urls")),
    path("api/v1/users/", include("user.urls")),
    path("api/v1/skills/", include("skill.urls")),
    path("api/v1/search/", include("search.urls")),
    path("api/v1/resumes/", include("resume.urls")),
    path("api/v1/recommendations/", include("recommendation.urls")),
    # Health Check
    path("health/", health_check, name="health_check"),
    # API Documentation (Spectacular)
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v1/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
