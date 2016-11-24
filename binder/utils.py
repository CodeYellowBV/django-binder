def force_download(response, filename=None, prefix='', suffix='', jquery_cookie=False):
	"""
	Take a Django HttpResponse object, and modify it to force the browser to
	save the response as a file named <prefix><filename><suffix>. Returns the
	response object.

	If <filename> is None, return the response object unmodified.

	This sets the "Content-Disposition" header on the response. It also strips
	out any characters that might cause trouble from the filename. This
	includes anything non-ascii, non-printable characters, forward and backward
	slashes, and leading dots.

	If <jquery_cookie> is True, also add a "fileDownload=true" cookie.
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

		response['Content-Disposition'] = 'attachment; filename="{}{}{}"'.format(prefix, filename, suffix)

		if jquery_cookie:
			response.set_cookie('fileDownload', 'true')

	return response
