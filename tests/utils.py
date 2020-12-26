from os import urandom
from tempfile import NamedTemporaryFile

from PIL import Image


IMG_SUFFIX = {
	'jpeg': '.jpg',
	'png': '.png',
}


def image(width, height):
	return Image.frombytes('RGB', (width, height), urandom(width * height * 3))


def temp_imagefile(width, height, format):
	i = image(width, height)
	f = NamedTemporaryFile(suffix=IMG_SUFFIX[format])
	i.save(f, format)
	f.seek(0)
	return f
