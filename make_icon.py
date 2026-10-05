from PIL import Image

img = Image.open("icon.png").convert("RGBA")

# Windows picks the right size for each context
sizes = [(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)]

img.save("icon.ico", format="ICO", sizes=sizes)
print("Done → icon.ico")