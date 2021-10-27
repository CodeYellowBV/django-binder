from os import urandom
from tempfile import NamedTemporaryFile

from PIL import Image


IMG_SUFFIX = {
	'jpeg': '.jpg',
	'png': '.png',
}
BYTES_PER_PIXEL = {
	'RGB': 3,
	'RGBA': 4,
}

def image(width, height, mode):
	return Image.frombytes(mode, (width, height), urandom(width * height * BYTES_PER_PIXEL[mode]))


def temp_imagefile(width, height, format, mode='RGB'):
	i = image(width, height, mode)
	f = NamedTemporaryFile(suffix=IMG_SUFFIX[format])
	i.save(f, format)
	f.seek(0)
	return f
