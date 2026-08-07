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


class SavePatternForm(forms.Form):
    title = forms.CharField(label="图纸名称", max_length=120)
    note = forms.CharField(label="备注", required=False, widget=forms.Textarea(attrs={"rows": 3}))
