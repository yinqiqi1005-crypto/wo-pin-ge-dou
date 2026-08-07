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


class ParameterAdjustmentForm(forms.Form):
    grid_size = forms.TypedChoiceField(
        label="图纸尺寸", choices=((30, "30×30"), (50, "50×50"), (70, "70×70")), coerce=int
    )
    color_limit = forms.TypedChoiceField(
        label="颜色数量", choices=((12, "12 色"), (24, "24 色"), (36, "36 色")), coerce=int
    )
    background_mode = forms.ChoiceField(
        label="背景处理",
        choices=(("keep", "保留背景"), ("simplify", "简化背景"), ("remove", "移除背景")),
    )


class PatternMetadataForm(forms.Form):
    title = forms.CharField(label="图纸名称", max_length=120)
    note = forms.CharField(label="备注", required=False, widget=forms.Textarea(attrs={"rows": 3}))
