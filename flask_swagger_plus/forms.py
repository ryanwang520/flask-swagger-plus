#!/usr/bin/env python
# -*- coding: utf-8 -*-


import functools
import types
import re

from flask.globals import _app_ctx_stack, request, _app_ctx_err_msg, LocalProxy

from .errors import ValidationError


_none_value = object()


def _lookup_current_form():
    top = _app_ctx_stack.top
    if top is None:
        raise RuntimeError(_app_ctx_err_msg)
    return getattr(top, 'form', None)


form = LocalProxy(_lookup_current_form)


class FormField:
    VALID_SOURCES = ('args', 'form', 'json', 'path')

    def __init__(self, source='', name='', required=True,
                 default=None, description='', enum=None):
        if source and source not in self.VALID_SOURCES:
            raise ValueError('request source %s is not valid' % source)
        self.source = source or 'json'
        self.required = required
        self.default = default
        self.description = description
        self.name = name
        self.enum = enum

    def __set__(self, instance, value):
        raise ValueError('form field attribute is readonly')

    def _get_request_data(self):
        if not hasattr(request, self.source):
            raise ValidationError(
                '%s is not a valid data source from request' % self.source)
        if self.source == 'path':
            return request.view_args[self.name]
        if self.source == 'json' and request.get_json(silent=True) is None:
            source = 'form'
        else:
            source = self.source
        req_data = getattr(request, source)
        # request.args or request.form
        if hasattr(req_data, 'getlist'):
            raw = req_data.getlist(self.name)
            if len(raw) == 1:
                return raw[0]
            if len(raw) == 0:
                return _none_value
            raise ValidationError(
                'multi values form field %s is not to be supported!' % self.name)
        # request.json
        return req_data.get(self.name, _none_value)

    def __get__(self, instance, _):
        if instance is None:
            return self
        name = self.name
        data = self._get_request_data()

        if data in (_none_value, ''):
            if self.required:
                raise ValidationError('FIELD %s is required' % name)
            return self.default

        result = self.process(data)
        if self.enum and result not in self.enum and self.required:
            raise ValidationError('FIELD {} must be a value of {}'.format(
                self.name, self.enum
            ))
        return result

    def process(self, data):
        return data


class LengthLimitedField(FormField):
    def __init__(self, source='', min_length=None, max_length=None,
                 trim=True, **kwargs):
        self.min = min_length
        self.max = max_length
        self.trim = trim
        super(LengthLimitedField, self).__init__(source, **kwargs)

    def process(self, data):
        if data is None:
            super(LengthLimitedField, self).process(data)
        if self.trim:
            data = data.strip()
        if self.max is not None and len(data) > self.max:
            raise ValidationError(
                'FIELD {} is limited to max length {} but get {}'.format(
                    self.name, self.max, len(data)))
        if self.min is not None and len(data) < self.min:
            raise ValidationError(
                'FIELD {} is limited to min length {} but get {}'.format(
                    self.name, self.min, len(data)))

        return super(LengthLimitedField, self).process(data)


class SizedField(FormField):
    def __init__(self, source='', min_val=None, max_val=None,
                 inc_min=True, inc_max=True, **kwargs):
        self.min = min_val
        self.max = max_val
        self.inc_min = inc_min
        self.inc_max = inc_max
        super(SizedField, self).__init__(source, **kwargs)

    def process(self, data):
        if self.max is not None:
            invalid = data > self.max if self.inc_max else data >= self.max
            if invalid:
                raise ValidationError(
                    'FIELD {} is limited to max value {} but get {}'.format(
                        self.name, self.max, data))
        if self.min is not None:
            invalid = data < self.min if self.inc_min else data <= self.min
            if invalid:
                raise ValidationError(
                    'FIELD {} is limited to min value {} but get {}'.format(
                        self.name, self.min, data))
        return super(SizedField, self).process(data)


class TypedField(FormField):
    field_type = type(None)

    def process(self, data):
        try:
            if data is not None:
                data = self.field_type(data)
            return super(TypedField, self).process(data)
        except (TypeError, ValueError):
            raise ValidationError(
                'FIELD {} cannot be converted to {}'.format(
                    self.name, self.field_type
                )
            )


class IntField(TypedField, SizedField):
    field_type = int


class FloatField(TypedField, SizedField):
    field_type = float


class BasicStringField(TypedField):
    field_type = str


class BoolField(TypedField):
    field_type = bool


class StringField(BasicStringField, LengthLimitedField):
    pass


class CSVListField(FormField):
    def __init__(self, source='', each_field=None, **kwargs):
        self.each_field = each_field
        super(CSVListField, self).__init__(source, **kwargs)

    def process(self, data):
        data_list = data.split(',')
        if isinstance(self.each_field, FormField):
            each_field = self.each_field
        else:
            each_field = self.each_field(source=self.source)
        return [each_field.process(elem) for elem in data_list]


class FormFieldMeta(type):
    VALIDATOR_FIELDS_NAME = '_validator_fields'

    def __new__(cls, name, bases, attrs):
        attrs[cls.VALIDATOR_FIELDS_NAME] = []
        for base in bases:
            if hasattr(base, cls.VALIDATOR_FIELDS_NAME):
                attrs[cls.VALIDATOR_FIELDS_NAME].extend(
                    getattr(base, cls.VALIDATOR_FIELDS_NAME))

        for field, value in attrs.items():
            if isinstance(value, FormField):
                value.name = field
                attrs[cls.VALIDATOR_FIELDS_NAME].append(field)
        return type.__new__(cls, name, bases, attrs)


def with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""

    # This requires a bit of explanation: the basic idea is to make a dummy
    # metaclass for one level of class instantiation that replaces itself with
    # the actual metaclass.
    class metaclass(meta):
        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)

    return type.__new__(metaclass, 'temporary_class', (), {})


class Form(with_metaclass(FormFieldMeta)):
    def __init__(self, view_func):
        self._view_func = view_func
        view_func.form = self
        functools.update_wrapper(self, view_func)

    def __call__(self, *args, **kwargs):
        # lazy load form data when accessing
        _app_ctx_stack.top.form = self
        self.after_loading_hook()
        return self._view_func(*args, **kwargs)

    def after_loading_hook(self):
        return

    def __get__(self, instance, _):
        if instance is None:
            return self
        return types.MethodType(self, instance)


SOURCE_MAP = {
    'json': 'formData',
    'form': 'formData',
    'args': 'query',
}

PY_2_SWAGGER_TYPE_MAP = {
    int: 'integer',
    str: 'string',
    float: 'number',
    bool: 'boolean',
}


def form_params(form):
    form_cls = form.__class__
    params = []
    for name in form_cls._validator_fields:
        field = getattr(form_cls, name)
        # TODO more extended types
        if field.__class__ in (CSVListField,):
            type = 'string'
        else:
            type = PY_2_SWAGGER_TYPE_MAP[field.field_type]
        param = {
            'name': name,
            'type': type,
            'in': SOURCE_MAP[field.source],
            'description': field.description

        }
        if field.default:
            param['default'] = field.default
        if field.enum:
            param['enum'] = list(field.enum)

        params.append(param)
    return params
