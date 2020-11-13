import warnings

from .decorators import view_logger


warnings.warn(
	(
		'importing view_logger from binder.view_logger is deprecated, '
		'view_logger should be imported from binder.decorators'
	),
	DeprecationWarning,
	stacklevel=2,
)

__all__ = ['view_logger']
