from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import UserProfile


class RegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)


class ProfileSettingsForm(forms.ModelForm):
    email = forms.EmailField(label="邮箱", required=False)

    LANGUAGE_CHOICES = (
        ("zh-Hans", "简体中文"),
        ("en", "English"),
        ("ja", "日本語"),
        ("ko", "한국어"),
    )
    SIZE_CHOICES = (
        ("29x29", "29×29"),
        ("29x58", "29×58"),
        ("58x29", "58×29"),
        ("58x58", "58×58"),
        ("58x87", "58×87"),
        ("87x58", "87×58"),
        ("87x87", "87×87"),
        ("87x116", "87×116"),
        ("116x87", "116×87"),
        ("116x116", "116×116"),
        ("14x14", "14×14（极简图标）"),
    )
    COLOR_CHOICES = ((12, "12 色"), (24, "24 色"), (36, "36 色"))
    BACKGROUND_CHOICES = (
        ("keep", "保留背景"),
        ("simplify", "简化背景"),
        ("remove", "移除背景"),
    )
    FINISHED_USE_CHOICES = (
        ("display", "装框展示"),
        ("daily", "挂件或日常使用"),
        ("flat", "杯垫等平面用品"),
        ("assembly", "大型拼接作品"),
        ("unsure", "不确定"),
    )

    preferred_language = forms.ChoiceField(label="界面语言", choices=LANGUAGE_CHOICES)
    default_pattern_size = forms.ChoiceField(label="默认图纸尺寸", choices=SIZE_CHOICES)
    default_color_limit = forms.TypedChoiceField(
        label="默认颜色数量", choices=COLOR_CHOICES, coerce=int
    )
    default_background_mode = forms.ChoiceField(label="默认背景处理", choices=BACKGROUND_CHOICES)
    default_finished_use = forms.ChoiceField(label="默认成品用途", choices=FINISHED_USE_CHOICES)

    class Meta:
        model = UserProfile
        fields = (
            "avatar",
            "display_name",
            "bio",
            "preferred_language",
            "default_pattern_size",
            "default_color_limit",
            "default_background_mode",
            "default_finished_use",
            "remember_creation_parameters",
        )
        labels = {"display_name": "昵称", "bio": "简介", "avatar": "头像"}
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["email"].initial = user.email

    def save(self, commit=True):
        profile = super().save(commit=commit)
        self.user.email = self.cleaned_data["email"]
        if commit:
            self.user.save(update_fields=("email",))
        return profile


class PatternCategoryForm(forms.Form):
    name = forms.CharField(label="分类名称", max_length=40)
    sort_order = forms.IntegerField(label="排序", min_value=0, max_value=999, required=False)
