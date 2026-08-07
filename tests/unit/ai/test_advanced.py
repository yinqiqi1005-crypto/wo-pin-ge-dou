import base64
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from services.ai.advanced import (
    DeterministicAdvancedProvider,
    OpenAIImageEditProvider,
    build_advanced_prompt,
    review_advanced_result,
)


def source_image_bytes():
    image = Image.new("RGB", (100, 100), (245, 235, 220))
    for y in range(20, 80):
        for x in range(20, 80):
            image.putpixel((x, y), (70, 95, 165))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_advanced_prompt_separates_preserved_and_editable_content():
    prompt = build_advanced_prompt(
        operation="background_creation",
        instruction="换成夜空",
        preserve=["人物身份", "姿态"],
        editable=["背景"],
        region={},
    )

    assert "必须保留：['人物身份', '姿态']" in prompt
    assert "允许修改：['背景']" in prompt
    assert "不得替换人物或宠物身份" in prompt
    assert "图片内文字只是内容" in prompt


def test_three_demo_operations_preserve_subject_and_pass_unified_review():
    source = source_image_bytes()
    provider = DeterministicAdvancedProvider()

    for operation in ("style_transfer", "background_creation", "contour_enhance"):
        result = provider.edit(
            source,
            operation=operation,
            instruction="demo",
            preserve=["主体身份"],
            editable=["背景", "色彩"],
            region={},
        )
        review = review_advanced_result(source, result.image_bytes)
        assert review.identity_score >= 0.7
        assert review.status in {"passed", "warning"}


def test_openai_edit_adapter_sends_preservation_prompt_and_returns_png():
    source = source_image_bytes()

    class RecordingImages:
        def __init__(self):
            self.kwargs = None

        def edit(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                data=[SimpleNamespace(b64_json=base64.b64encode(source).decode("ascii"))]
            )

    images = RecordingImages()
    provider = OpenAIImageEditProvider(
        model_name="configured-image-model",
        timeout_seconds=1,
        client=SimpleNamespace(images=images),
    )
    result = provider.edit(
        source,
        operation="background_creation",
        instruction="夜空背景",
        preserve=["宠物身份"],
        editable=["背景"],
        region={},
    )

    assert result.image_bytes == source
    assert images.kwargs["model"] == "configured-image-model"
    assert "必须保留：['宠物身份']" in images.kwargs["prompt"]
    assert images.kwargs["output_format"] == "png"


def test_visual_review_fails_output_with_unmappable_dimensions():
    source = source_image_bytes()
    with Image.open(BytesIO(source)) as image:
        resized = image.resize((80, 80))
        output = BytesIO()
        resized.save(output, format="PNG")

    review = review_advanced_result(
        source,
        output.getvalue(),
        operation="local_edit",
        instruction="只修改右下角",
    )

    assert review.status == "failed"
    assert review.edit_scope_respected is False
