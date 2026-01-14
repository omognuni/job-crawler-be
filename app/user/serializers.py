from django.contrib.auth import authenticate
from rest_framework import serializers
from user.models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
        help_text="최소 8자 이상의 비밀번호를 입력하세요.",
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_password(self, value):
        """
        비밀번호 복잡도 검증
        """
        if len(value) < 8:
            raise serializers.ValidationError("비밀번호는 최소 8자 이상이어야 합니다.")
        if value.isdigit():
            raise serializers.ValidationError(
                "비밀번호는 숫자만으로 구성될 수 없습니다."
            )
        if value.isalpha():
            raise serializers.ValidationError(
                "비밀번호는 문자만으로 구성될 수 없습니다."
            )
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        if username and password:
            user = authenticate(
                request=self.context.get("request"),
                username=username,
                password=password,
            )
            if not user:
                raise serializers.ValidationError("Invalid credentials")
        else:
            raise serializers.ValidationError("Must include 'username' and 'password'")

        data["user"] = user
        return data


class GoogleOAuthStartSerializer(serializers.Serializer):
    """
    Google OAuth 시작 요청 serializer (SCRUM-21)
    """

    redirect_uri = serializers.URLField(max_length=500)


class GoogleOAuthCallbackSerializer(serializers.Serializer):
    """
    Google OAuth 콜백 처리 요청 serializer (SCRUM-23)
    """

    code = serializers.CharField(max_length=2000)
    state = serializers.CharField(max_length=2000)
