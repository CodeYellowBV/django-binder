from django.db.models import TextField
from html.parser import HTMLParser
from django.core import exceptions
from django.utils.translation import gettext as _


def link_validator(tag, attribute_name, attribute_value):
	if not attribute_value.startswith('http://') and not attribute_value.startswith('https://'):
		raise exceptions.ValidationError(
			_('Link is not valid'),
			code='invalid_attribute',
			params={
				'tag': tag,
			},
		)


class HtmlValidator(HTMLParser):
	allowed_tags = [
		# General setup
		'p', 'br',
		# Headers
		'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7',

		# text decoration
		'b', 'strong', 'i', 'em', 'u',
		# Lists
		'ol', 'ul', 'li',

		# Special
		'a',
	]

	allowed_attributes = {
		'a': ['href', 'rel', 'target']
	}

	special_validators = {
		('a', 'href'): link_validator
	}

	error_messages = {
		'invalid_tag': _('Tag %(tag)s is not allowed'),
		'invalid_attribute': _('Attribute %(attribute)s not allowed for tag %(tag)s'),
	}

	def handle_starttag(self, tag: str, attrs: list) -> None:
		if tag not in self.allowed_tags:
			raise exceptions.ValidationError(
				self.error_messages['invalid_tag'],
				code='invalid_tag',
				params={
					'tag': tag
				},
			)

		allowed_attributes_for_tag = self.allowed_attributes.get(tag, [])

		for (attribute_name, attribute_content) in attrs:
			if attribute_name not in allowed_attributes_for_tag:
				raise exceptions.ValidationError(
					self.error_messages['invalid_attribute'],
					code='invalid_attribute',
					params={
						'tag': tag,
						'attribute': attribute_name
					},
				)
			if (tag, attribute_name) in self.special_validators:
				self.special_validators[(tag, attribute_name)](tag, attribute_name, attribute_content)


class HtmlField(TextField):
	"""
	Determine a safe way to save "secure" user provided HTML input, and prevent XSS injections
	"""

	def validate(self, value, _):
		# Validate all html tags
		validator = HtmlValidator()
		validator.feed(value)
