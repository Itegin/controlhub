from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (180, 180), "#0B0D10")
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 72)
except:
    font = ImageFont.load_default()

text = "CH"
bbox = draw.textbbox((0, 0), text, font=font)
w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
draw.text(((180 - w) / 2, (180 - h) / 2 - bbox[1]), text, fill="#0D9488", font=font)

img.save("frontend/icons/apple-touch-icon.png")
print("done")
