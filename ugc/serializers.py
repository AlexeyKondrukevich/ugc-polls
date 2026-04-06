from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import AnswerOption, Poll, Question, UserAnswer

User = get_user_model()


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ("id", "text", "weight")


class QuestionSerializer(serializers.ModelSerializer):
    options = AnswerOptionSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Question
        fields = (
            "id",
            "text",
            "weight",
            "allow_custom_answer",
            "options",
        )


class PollSerializer(serializers.ModelSerializer):
    questions_count = serializers.IntegerField(
        source="questions.count",
        read_only=True,
    )

    class Meta:
        model = Poll
        fields = (
            "id",
            "title",
            "author",
            "created_at",
            "questions_count",
        )


class PollDetailSerializer(PollSerializer):
    questions = QuestionSerializer(
        many=True,
        read_only=True,
    )

    class Meta(PollSerializer.Meta):
        fields = PollSerializer.Meta.fields + ("questions",)


class UserAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAnswer
        fields = (
            "id",
            "session",
            "question",
            "selected_option",
            "custom_text",
        )
        read_only_fields = (
            "id",
            "answered_at",
        )
        extra_kwargs = {
            "selected_option": {"required": False, "allow_null": True},
            "custom_text": {"required": False, "allow_blank": True},
        }

    def validate(self, data):
        if not data.get("selected_option") and not data.get("custom_text"):
            msg = _(
                """Требуется либо вариант ответа, """ """либо свой ответ"""
            )
            raise serializers.ValidationError(msg)

        if data.get("selected_option") and data.get("custom_text"):
            msg = _(
                "Невозможно одновременно указать вариант ответа и свой ответ"
            )
            raise serializers.ValidationError(msg)

        selected_option = data.get("selected_option")
        question = data.get("question")
        if (
            selected_option
            and question
            and selected_option.question_id != question.id
        ):
            raise serializers.ValidationError(
                _(
                    "Выбранный вариант ответа не относится к указанному вопросу."
                )
            )

        return data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "password2",
            "email",
            "first_name",
            "last_name",
        )

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            msg = _("Пароли не совпадают")
            raise serializers.ValidationError({"password": msg})
        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        user.set_password(validated_data["password"])
        user.save()
        return user


class SubmitAnswerInputSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(
        help_text="ID вопроса, на который отвечаете"
    )
    selected_option = serializers.IntegerField(
        required=False, allow_null=True, help_text="ID выбранного варианта"
    )
    custom_text = serializers.CharField(
        required=False, allow_blank=True, help_text="Собственный ответ"
    )

    def validate(self, data):
        if not data.get("selected_option") and not data.get("custom_text"):
            msg = _(
                """Требуется либо вариант ответа, """ """либо свой ответ"""
            )
            raise serializers.ValidationError(msg)

        if data.get("selected_option") and data.get("custom_text"):
            msg = _(
                "Невозможно одновременно указать вариант ответа и свой ответ"
            )
            raise serializers.ValidationError(msg)
        return data
