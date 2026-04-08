import nested_admin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import AnswerOption, Poll, PollSession, Question, User, UserAnswer


class AnswerOptionInline(nested_admin.NestedStackedInline):
    model = AnswerOption
    extra = 1
    classes = ("collapse",)
    sortable_field_name = "weight"


class QuestionInline(nested_admin.NestedStackedInline):
    model = Question
    extra = 1
    classes = ("collapse",)
    sortable_field_name = "weight"
    inlines = (AnswerOptionInline,)


@admin.register(Poll)
class PollAdmin(nested_admin.NestedModelAdmin):
    list_display = ("id", "title", "author", "created_at")
    list_select_related = ("author",)
    raw_id_fields = ("author",)
    search_fields = ("title",)
    inlines = (QuestionInline,)
    date_hierarchy = "created_at"


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_select_related = (
        "session__user",
        "session__poll",
        "question",
        "selected_option",
    )
    list_display = (
        "id",
        "session_user",
        "session_poll",
        "question",
        "selected_option",
        "answered_at",
    )
    raw_id_fields = ("session", "question", "selected_option")

    def session_user(self, obj):
        return obj.session.user.username

    session_user.short_description = _("Пользователь")

    def session_poll(self, obj):
        return obj.session.poll.title

    session_poll.short_description = _("Опрос")


@admin.register(PollSession)
class PollSessionAdmin(admin.ModelAdmin):
    list_select_related = ("user", "poll", "current_question")
    raw_id_fields = ("user", "poll", "current_question")


admin.site.register(User, UserAdmin)
