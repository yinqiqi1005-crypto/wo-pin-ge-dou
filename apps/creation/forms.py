from django import forms

from .models import GenerationSettings

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class ImageUploadForm(forms.Form):
    image = forms.ImageField(
        label="选择图片",
        error_messages={
            "invalid_image": "请上传一张有效的 JPG 或 PNG 图片，文件不能损坏。",
        },
    )

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("图片不能超过 10 MB。")
        if image.content_type not in {"image/jpeg", "image/png"}:
            raise forms.ValidationError("当前只支持 JPG 和 PNG 图片。")
        return image


class GenerationSettingsForm(forms.ModelForm):
    GRID_CHOICES = ((30, "30×30"), (50, "50×50"), (70, "70×70"))
    COLOR_CHOICES = ((12, "12 色"), (24, "24 色"), (36, "36 色"))
    BACKGROUND_CHOICES = (
        ("keep", "保留背景"),
        ("simplify", "简化背景"),
        ("remove", "移除背景"),
    )

    grid_size = forms.TypedChoiceField(label="图纸尺寸", choices=GRID_CHOICES, coerce=int)
    color_limit = forms.TypedChoiceField(label="颜色数量", choices=COLOR_CHOICES, coerce=int)
    background_mode = forms.ChoiceField(label="背景处理", choices=BACKGROUND_CHOICES)

    class Meta:
        model = GenerationSettings
        fields = ("grid_size", "color_limit", "background_mode")

    def __init__(self, *args, has_subject=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_subject = has_subject

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("background_mode") == "remove" and not self.has_subject:
            self.add_error("background_mode", "未识别到主体时不能移除背景，请先选择主体。")
        return cleaned


class SubjectSelectionForm(forms.Form):
    x = forms.FloatField(label="主体左边界", min_value=0, max_value=1)
    y = forms.FloatField(label="主体上边界", min_value=0, max_value=1)
    width = forms.FloatField(label="主体宽度", min_value=0.01, max_value=1)
    height = forms.FloatField(label="主体高度", min_value=0.01, max_value=1)

    def clean(self):
        cleaned = super().clean()
        if not self.errors:
            if cleaned["x"] + cleaned["width"] > 1:
                raise forms.ValidationError("主体区域不能超出图片右侧。")
            if cleaned["y"] + cleaned["height"] > 1:
                raise forms.ValidationError("主体区域不能超出图片底部。")
        return cleaned


class SavePatternForm(forms.Form):
    title = forms.CharField(label="图纸名称", max_length=120)
    note = forms.CharField(label="备注", required=False, widget=forms.Textarea(attrs={"rows": 3}))
