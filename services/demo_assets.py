from io import BytesIO

from PIL import Image, ImageDraw


def build_demo_images():
    definitions = (
        ("demo-person.png", "人物", (225, 100, 85)),
        ("demo-pet.png", "宠物", (80, 115, 185)),
        ("demo-object.png", "物品", (80, 155, 115)),
    )
    for filename, label, color in definitions:
        image = Image.new("RGB", (512, 512), (247, 242, 234))
        draw = ImageDraw.Draw(image)
        if label == "人物":
            draw.ellipse((176, 65, 336, 225), fill=color)
            draw.rounded_rectangle((130, 210, 382, 470), radius=50, fill=color)
        elif label == "宠物":
            draw.polygon(((125, 190), (175, 55), (230, 185)), fill=color)
            draw.polygon(((282, 185), (337, 55), (390, 190)), fill=color)
            draw.ellipse((105, 145, 407, 445), fill=color)
        else:
            draw.rounded_rectangle((100, 115, 412, 425), radius=55, fill=color)
            draw.rectangle((205, 55, 307, 135), fill=color)
        output = BytesIO()
        image.save(output, format="PNG")
        yield filename, label, output.getvalue()
