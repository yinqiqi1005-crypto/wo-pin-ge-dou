from django import forms

from apps.creation.models import AdvancedOperation
from apps.memberships.models import FeatureCode

OPERATION_FEATURES = {
    AdvancedOperation.STYLE_TRANSFER: FeatureCode.STYLE_TRANSFER,
    AdvancedOperation.BACKGROUND_CREATION: FeatureCode.BACKGROUND_CREATION,
    AdvancedOperation.CONTOUR_ENHANCE: FeatureCode.COMPOSITION,
    AdvancedOperation.ELEMENT_EDIT: FeatureCode.ELEMENT_EDIT,
    AdvancedOperation.LOCAL_EDIT: FeatureCode.LOCAL_EDIT,
}


class AdvancedCreationForm(forms.Form):
    operation = forms.ChoiceField(label="创作类型", choices=AdvancedOperation.choices)
    instruction = forms.CharField(
        label="创作要求",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    preserve_content = forms.CharField(
        label="必须保留",
        initial="主体身份,姿态,关键特征",
        help_text="用逗号分隔。",
    )
    editable_content = forms.CharField(
        label="允许修改",
        initial="背景,色彩,装饰细节",
        help_text="用逗号分隔。",
    )
    region_x = forms.FloatField(label="局部区域左边界", min_value=0, max_value=1, required=False)
    region_y = forms.FloatField(label="局部区域上边界", min_value=0, max_value=1, required=False)
    region_width = forms.FloatField(
        label="局部区域宽度", min_value=0.01, max_value=1, required=False
    )
    region_height = forms.FloatField(
        label="局部区域高度", min_value=0.01, max_value=1, required=False
    )

    def __init__(self, *args, enabled_features=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled_features = set(enabled_features)
        self.fields["operation"].choices = [
            choice
            for choice in AdvancedOperation.choices
            if OPERATION_FEATURES[choice[0]] in self.enabled_features
        ]

    @staticmethod
    def split_items(value):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]

    def clean(self):
        cleaned = super().clean()
        region_keys = ("region_x", "region_y", "region_width", "region_height")
        values = [cleaned.get(key) for key in region_keys]
        if cleaned.get("operation") == AdvancedOperation.LOCAL_EDIT and any(
            value is None for value in values
        ):
            raise forms.ValidationError("局部编辑必须完整填写编辑区域。")
        if all(value is not None for value in values):
            if cleaned["region_x"] + cleaned["region_width"] > 1:
                raise forms.ValidationError("局部编辑区域不能超出图片右侧。")
            if cleaned["region_y"] + cleaned["region_height"] > 1:
                raise forms.ValidationError("局部编辑区域不能超出图片底部。")
        return cleaned

    def edit_region(self):
        keys = ("x", "y", "width", "height")
        values = [
            self.cleaned_data.get("region_x"),
            self.cleaned_data.get("region_y"),
            self.cleaned_data.get("region_width"),
            self.cleaned_data.get("region_height"),
        ]
        return (
            dict(zip(keys, values, strict=True))
            if all(value is not None for value in values)
            else {}
        )


class ParameterAdjustmentForm(forms.Form):
    grid_size = forms.TypedChoiceField(
        label="图纸尺寸", choices=((30, "30×30"), (50, "50×50"), (70, "70×70")), coerce=int
    )
    color_limit = forms.TypedChoiceField(
        label="颜色数量",
        choices=(
            (12, "12 色上限"),
            (18, "18 色上限"),
            (24, "24 色上限"),
            (30, "30 色上限"),
            (36, "36 色上限"),
        ),
        coerce=int,
    )
    background_mode = forms.ChoiceField(
        label="背景处理",
        choices=(("keep", "保留背景"), ("simplify", "简化背景"), ("remove", "移除背景")),
    )


class PatternMetadataForm(forms.Form):
    title = forms.CharField(label="图纸名称", max_length=120)
    note = forms.CharField(label="备注", required=False, widget=forms.Textarea(attrs={"rows": 3}))
