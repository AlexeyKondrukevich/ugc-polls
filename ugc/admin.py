import nested_admin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AnswerOption,
    Poll,
    PollSession,
    Question,
    User,
    UserAnswer,
)


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
    list_display = ("title", "author", "created_at")
    list_filter = ("author",)
    search_fields = ("title",)
    inlines = (QuestionInline,)


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    pass


@admin.register(PollSession)
class PollSessionAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, UserAdmin)
