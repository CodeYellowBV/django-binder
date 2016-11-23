def force_download(response, filename=None):
	"""
	Take a Django HttpResponse object, and modify it to force the browser to save
	the response as a file. The file will be named <filename> (if specified).

	This sets the "Content-Disposition" header on the response. It also strips out
	any characters that might cause trouble from the filename. This includes any-
	thing non-ascii, non-printable characters, forward and backward slashes, and
	leading dots.
	"""
	if filename:
		# HTTP header content is ill-defined; we strip out anything that might not work
		# Limit to ascii
		filename = filename.encode('ascii', errors='ignore').decode()
		# Filter non-printable characters (including \r\n\t)
		filename = ''.join(c for c in filename if c.isprintable())
		# No backslashes please. Also no forward slashes in filenames.
		filename = filename.replace('\\', '')
		filename = filename.replace('/', '')
		# Finally, strip leading dots. They don't make sense in filenames, and may lead to hidden files on Unices
		filename = filename.lstrip('.')

		response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
	else:
		response['Content-Disposition'] = 'attachment'
