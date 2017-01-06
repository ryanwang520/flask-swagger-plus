#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
import functools

from marshmallow import Schema
from marshmallow.fields import (
    Nested, List, String, Date, Boolean, Dict, Function, Method
    )
from decimal import Decimal

TYPE_MAP = {
    int: 'integer',
    float: 'number',
    Decimal: 'number'
}


def extract_from_field(field):
    """
    extract swagger property from a single field
    """
    if isinstance(field, (String, Date)):
        return 'string'
    if isinstance(field, Boolean):
        return 'boolean'
    elif hasattr(field, 'num_type'):
        return TYPE_MAP[field.num_type]
    if isinstance(field, Dict):
        return 'object'
    raise ValueError('type for {} is not supported'.format(field))


def schema_to_swagger_properties(schema):
    fields = schema._declared_fields
    if schema.only:
        keys = schema.only
    elif schema.exclude:
        keys = tuple([_ for _ in fields.keys() if _ not in schema.exclude])
    else:
        keys = tuple(fields.keys())

    result = {}
    for key in keys:
        raw_field = fields[key]
        if isinstance(raw_field, (Function, Method)):
            field = raw_field.metadata.get('field')
            if not field:
                continue
        else:
            field = raw_field

        if Nested in field.__class__.__mro__:
            if field.nested == 'self':
                nested_schema = schema.__class__
            else:
                nested_schema = field.nested

            many = field.many
            result[key] = extract_schema(
                nested_schema(only=field.only, exclude=(key,)), many=many)['schema']
            # properties would not contain `id` field
            if not many:
                del result[key]['id']
        elif List in field.__class__.__mro__:
            result[key] = {
                'type': 'array',
                'items': {
                    'type': extract_from_field(field.container)
                }
            }
        else:
            obj = result[key] = {}
            s = extract_from_field(field)
            obj['type'] = s
    return result


def extract_schema(schema, many, nested=False):
    if many:
        return {
            'schema': {
                'type': 'array',
                'items': extract_schema(schema, many=False, nested=True)
            }
        }

    properties = schema_to_swagger_properties(schema)
    schema_id = schema.__class__.__name__
    if nested:
        schema_id = '{}{}'.format(schema_id, uuid.uuid4().hex)
    return {
        'schema': {
            'properties': properties,
            'id': schema_id
        }
    }


class SwaggerResponse(object):
    def __init__(self, schema, status=200):
        """

        :param schema: `Schema` class or instance
        :param status: associated http status code
        """
        if not isinstance(schema, Schema):
            self.schema = schema()
        else:
            self.schema = schema
        self.status = status

    def attach_responses(self, func):
        responses = {str(self.status): {
            'description': 'api result'
        }}
        response = responses[(str(self.status))]

        response.update(extract_schema(self.schema, many=self.schema.many))

        func.swagger_responses = responses

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        self.attach_responses(wrapper)

        return wrapper
