from django import forms

from .ironing import IRONING_STYLES
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
    PATTERN_SIZE_CHOICES = (
        ("29x29", "29×29 · 1 块拼板"),
        ("29x58", "29×58 · 2 块竖版"),
        ("58x29", "58×29 · 2 块横版"),
        ("58x58", "58×58 · 4 块拼板"),
        ("58x87", "58×87 · 6 块竖版"),
        ("87x58", "87×58 · 6 块横版"),
        ("87x87", "87×87 · 9 块拼板"),
        ("87x116", "87×116 · 12 块竖版"),
        ("116x87", "116×87 · 12 块横版"),
        ("116x116", "116×116 · 16 块拼板"),
        ("14x14", "14×14 · 极简图标"),
    )
    COLOR_CHOICES = (
        (12, "12 色上限 · 简洁图标"),
        (18, "18 色上限 · 简约插画"),
        (24, "24 色上限 · 常用照片"),
        (30, "30 色上限 · 丰富层次"),
        (36, "36 色上限 · 通用色板全量"),
    )
    BACKGROUND_CHOICES = (
        ("keep", "保留背景"),
        ("simplify", "简化背景"),
        ("remove", "移除背景"),
    )

    grid_size = forms.IntegerField(required=False, widget=forms.HiddenInput())
    pattern_size = forms.ChoiceField(label="图纸尺寸", choices=PATTERN_SIZE_CHOICES, required=False)
    face_mode = forms.ChoiceField(
        label="人物生成模式",
        choices=(("face_detail", "脸部细节优先"), ("composition", "整体构图优先")),
        required=False,
    )
    finished_use = forms.ChoiceField(
        label="成品用途",
        choices=(
            ("display", "装框展示"),
            ("daily", "挂件或日常使用"),
            ("flat", "杯垫等平面用品"),
            ("assembly", "大型拼接作品"),
            ("unsure", "不确定"),
        ),
        required=False,
    )
    ironing_style = forms.ChoiceField(
        label="烫豆方式",
        choices=[(code, style["name"]) for code, style in IRONING_STYLES.items()],
        widget=forms.RadioSelect,
        help_text="由你选择；图纸保存后会记录这项制作方式。",
        required=False,
    )
    color_limit = forms.TypedChoiceField(label="颜色数量", choices=COLOR_CHOICES, coerce=int)
    background_mode = forms.ChoiceField(label="背景处理", choices=BACKGROUND_CHOICES)

    class Meta:
        model = GenerationSettings
        fields = (
            "grid_size",
            "grid_width",
            "grid_height",
            "color_limit",
            "background_mode",
            "face_mode",
            "finished_use",
            "ironing_style",
        )
        widgets = {"grid_width": forms.HiddenInput(), "grid_height": forms.HiddenInput()}

    def __init__(self, *args, has_subject=True, enabled_options=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_subject = has_subject
        self.fields["grid_width"].required = False
        self.fields["grid_height"].required = False
        width = self.instance.grid_width or self.instance.grid_size
        height = self.instance.grid_height or self.instance.grid_size
        self.fields["pattern_size"].initial = f"{width}x{height}"
        self.fields["face_mode"].initial = self.instance.face_mode
        self.fields["finished_use"].initial = self.instance.finished_use
        self.fields["ironing_style"].initial = self.instance.ironing_style
        enabled_options = enabled_options or {}
        if enabled_options:
            configured_limits = enabled_options.get("color_limits", [])
            # Upgrade the original three-option demo without overriding a later
            # administrator's deliberately customised list.
            if configured_limits == [12, 24, 36]:
                configured_limits = [choice[0] for choice in self.COLOR_CHOICES]
            self.fields["color_limit"].choices = [
                (value, dict(self.COLOR_CHOICES).get(value, f"{value} 色上限"))
                for value in configured_limits
            ]
            background_labels = dict(self.BACKGROUND_CHOICES)
            self.fields["background_mode"].choices = [
                (value, background_labels[value])
                for value in enabled_options.get("background_modes", [])
                if value in background_labels
            ]

    def clean(self):
        cleaned = super().clean()
        pattern_size = cleaned.get("pattern_size")
        legacy_size = self.data.get("grid_size") if self.is_bound else None
        if pattern_size:
            width, height = (int(value) for value in pattern_size.split("x", maxsplit=1))
        elif legacy_size:
            width = height = int(legacy_size)
        else:
            width = self.instance.grid_width or self.instance.grid_size
            height = self.instance.grid_height or self.instance.grid_size
        cleaned["grid_width"] = width
        cleaned["grid_height"] = height
        cleaned["grid_size"] = max(width, height)
        cleaned["face_mode"] = cleaned.get("face_mode") or "composition"
        cleaned["finished_use"] = cleaned.get("finished_use") or "unsure"
        cleaned["ironing_style"] = cleaned.get("ironing_style") or "regular"
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
    category_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    note = forms.CharField(label="备注", required=False, widget=forms.Textarea(attrs={"rows": 3}))
