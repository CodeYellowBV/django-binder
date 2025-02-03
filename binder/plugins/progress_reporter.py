from abc import ABCMeta


class ProgressReporterInterface(metaclass=ABCMeta):
	"""
	Generic progress reporter interface
	"""

	def report(self, percentage_done: float) -> None:
		"""
		Report that we have done a certain percentage (0 <= percentage <= 1)
		"""
		pass

	def report_finished(self):
		"""
		Called when everything is done.
		"""
		return self.report(1)


class ProgressReporter(ProgressReporterInterface):
	"""
	A very basic progress reporter. Propagates the percentage door to a set of websocket rooms. This allows the frontend
	to listen to the progress.

	Usage example

	```
	progress_reporter = ProgressReporter(targets=[
        {
            'target': 'download',
            'uuid': download.uuid,
            'triggered_by': '*'
        },
        {
            'target': 'download',
            'uuid': download.uuid,
            'triggered_by': download.triggered_by.pk
        }
    ])

	# 20% done
    progress_reporter.report(0.2)

    # 50% done
    progress_reporter.report(0.5)

    # 100% done
    progress_reporter.report_finished()
    ````
	"""
	def __init__(self, targets: List[dict]):
		self.targets = targets

	def report(self, percentage_done: float):
		if not (0 <= percentage_done <= 1):
			raise Exception("percentage_done must be between 0 and 1")

		# For testing purposes
		if settings.DEBUG:
			from time import sleep
			sleep(0.5)

		trigger({
			'percentage_done': percentage_done
		}, self.targets)

	def report_finished(self):
		return self.report(1)
