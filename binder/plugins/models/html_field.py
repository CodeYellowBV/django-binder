from functools import reduce
from typing import List

from django.db.models import TextField
from html.parser import HTMLParser
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

ALLOWED_LINK_PREFIXES = [
	'http://',
	'https://',
	'mailto:'
]


def link_rel_validator(tag, attribute_name, attribute_value) -> List[ValidationError]:
	validation_errors = []

	rels = attribute_value.split(' ')

	if 'noopener' not in rels:

		validation_errors.append(ValidationError(
			_('Link needs rel="noopener"'),
			code='invalid_attribute',
			params={
				'tag': tag,
			},
		))

	if 'noreferrer' not in rels:
		validation_errors.append(ValidationError(
			_('Link needs rel="noreferer"'),
			code='invalid_attribute',
			params={
				'tag': tag,
			},
		))


	return validation_errors


def link_validator(tag, attribute_name, attribute_value) -> List[ValidationError]:
	validation_errors = []
	if not any(map(lambda prefix: attribute_value.startswith(prefix), ALLOWED_LINK_PREFIXES)):
		validation_errors.append(ValidationError(
			_('Link is not valid'),
			code='invalid_attribute',
			params={
				'tag': tag,
			},
		))
	return validation_errors


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

	required_attributes = {
		'a': ['rel'],
	}

	special_validators = {
		('a', 'href'): link_validator,
		('a', 'rel'): link_rel_validator,
	}

	error_messages = {
		'invalid_tag': _('Tag %(tag)s is not allowed'),
		'missing_attribute': _('Attribute %(attribute)s is required for tag %(tag)s'),
		'invalid_attribute': _('Attribute %(attribute)s not allowed for tag %(tag)s'),
	}

	def validate(self, value: str) -> List[ValidationError]:
		"""
		Validates html, and gives a list of validation errors
		"""

		self.errors = []

		self.feed(value)

		return self.errors

	def handle_starttag(self, tag: str, attrs: list) -> None:
		tag_errors = []
		if tag not in self.allowed_tags:
			tag_errors.append(ValidationError(
				self.error_messages['invalid_tag'],
				code='invalid_tag',
				params={
					'tag': tag
				},
			))

		set_attributes = set(map(lambda attr: attr[0], attrs))
		required_attributes = set(self.required_attributes.get(tag, []))
		missing_attributes = required_attributes - set_attributes
		for missing_attribute in missing_attributes:
			tag_errors.append(
				ValidationError(
					self.error_messages['missing_attribute'],
					code='missing_attribute',
					params={
						'tag': tag,
						'attribute': missing_attribute
					},
				)
			)

		allowed_attributes_for_tag = self.allowed_attributes.get(tag, [])

		for (attribute_name, attribute_content) in attrs:
			if attribute_name not in allowed_attributes_for_tag:
				tag_errors.append(ValidationError(
					self.error_messages['invalid_attribute'],
					code='invalid_attribute',
					params={
						'tag': tag,
						'attribute': attribute_name
					},
				))
			if (tag, attribute_name) in self.special_validators:
				tag_errors += self.special_validators[(tag, attribute_name)](tag, attribute_name, attribute_content)

		self.errors += tag_errors


class HtmlField(TextField):
	"""
	Determine a safe way to save "secure" user provided HTML input, and prevent XSS injections
	"""

	def validate(self, value: str, _):
		# Validate all html tags
		validator = HtmlValidator()
		errors = validator.validate(value)

		if errors:
			raise ValidationError(errors)
