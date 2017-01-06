#!/usr/bin/env python
# -*- coding: utf-8 -*-
import copy

import inspect
import sys
import re
from collections import defaultdict

import yaml

from .forms import form_params


def _sanitize(comment):
    return comment.replace('\n', '<br/>') if comment else comment


def _parse_docstring(obj):
    """
    parse api docstring to get corresponding summary， description and swagger
    content(responses & parameters)
    """

    def parse_doc(doc):
        first_line, other_lines, swag = None, None, None
        if doc:
            line_feed = doc.find('\n')
            if line_feed != -1:
                first_line = _sanitize(doc[:line_feed])
                yaml_sep = doc[line_feed + 1:].find('---')
                if yaml_sep != -1:
                    other_lines = _sanitize(
                        doc[line_feed + 1:line_feed + yaml_sep]
                    )
                    swag = yaml.load(doc[line_feed + yaml_sep:]) or {}
                else:
                    other_lines = _sanitize(doc[line_feed + 1:])
            else:
                first_line = doc
        if first_line is not None and not first_line.strip():
            first_line = other_lines
        return first_line, other_lines, swag

    full_doc = inspect.getdoc(obj)
    if not full_doc:
        return None, None, None
    return parse_doc(full_doc)


def _extract_definitions(alist, level=None, namespace=''):
    """
    extract swagger definitions recursively
    """

    def _extract_array_defs(source):
        # extract any definitions that are within arrays
        # this occurs recursively
        ret = []
        items = source.get('items')
        if items is not None and 'schema' in items and source.get('type') == 'array':
            ret += _extract_definitions([items], level + 1, namespace=namespace)
        return ret

    # for tracking level of recursion
    if level is None:
        level = 0

    defs = []
    if alist is not None:
        for item in alist:
            schema = item.get('schema')
            if schema is not None:
                schema_id = schema.get('id')
                if schema_id is not None:
                    defs.append(schema)
                    # id to `$ref`
                    ref = {"$ref": "#/definitions/{}".format(
                        ':'.join([namespace, schema_id]))}

                    if level == 0:
                        item['schema'] = ref
                    else:
                        item.update(ref)
                        del item['schema']

                # extract any definitions that are within properties
                # this occurs recursively
                properties = schema.get('properties')
                if properties is not None:
                    defs += _extract_definitions(
                        properties.values(), level + 1, namespace=namespace
                    )

                defs += _extract_array_defs(schema)

            defs += _extract_array_defs(item)

    return defs


PATH_2_SWAGGER_TYPE_MAP = {
    'int': 'integer',
    'string': 'string',
    'float': 'number',
}


def _extract_path_param(key, type_):
    return {
        'name': key,
        'type': 'string' if not type_ else PATH_2_SWAGGER_TYPE_MAP[type_],
        'in': 'path',
        'required': True,
        'description': key,
    }


def default_response(verb):
    """
    reasonable default response
    """
    if verb == 'post':
        return {
            '201': {'description': 'success'}
        }
    if verb in ('patch', 'delete', 'put'):
        return {
            '204': {'description': 'success'}
        }
    return {
        '200': {'description': 'api result'}
    }


_ignore_verbs = {"HEAD", "OPTIONS"}

# technically only responses is non-optional
_optional_fields = ['tags', 'consumes', 'produces', 'schemes', 'security',
                    'deprecated', 'operationId', 'externalDocs']


def _group_endpoints_by_http_verb(endpoint, methods):
    result = {}
    for verb in methods.difference(_ignore_verbs):
        if hasattr(endpoint, 'methods') and verb in endpoint.methods:
            verb = verb.lower()
            result[verb] = getattr(endpoint.view_class, verb)
        else:
            result[verb.lower()] = endpoint
    return result


def get_class_that_defined_method(meth):
    if inspect.ismethod(meth):
        for cls in inspect.getmro(meth.__self__.__class__):
            if cls.__dict__.get(meth.__name__) is meth:
                return cls
        meth = meth.__func__
    if inspect.isfunction(meth):
        cls = getattr(inspect.getmodule(meth),
                      meth.__name__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
        if isinstance(cls, type):
            return cls
    return None


def _complete_tags(swag, view):
    if 'tags' not in swag:
        try:
            view_class = get_class_that_defined_method(view)
            tags_in_endpoint = getattr(view_class, 'TAGS', None)
        except AttributeError:
            tags_in_endpoint = None
        tags = tags_in_endpoint or getattr(
            sys.modules[view.__module__], 'TAGS', [view.__module__])
        swag['tags'] = tags


def _complete_security(swag, view):
    if 'security' not in swag:
        swag['security'] = []
    if getattr(view, 'swagger_need_login', False):
        swag['security'] = [{'Bearer': []}]
    if getattr(view, 'swagger_optional_login', False):
        swag['security'] = [{'Bearer': []}]


def _complete_params(params, view, rule):
    """
    extract param defs from form and path
    """
    path = str(rule)
    for arg in re.findall('(<([^<>]*:)?([^<>]*)>)', path):
        type_, name = arg[1], arg[2]
        if type_:
            type_ = type_[:-1]
        params.append(_extract_path_param(name, type_))
    form = getattr(view, 'form', None)
    if form:
        params.extend(form_params(form))


def _complete_responses(responses, view, verb):
    if hasattr(view, 'swagger_responses'):
        responses.update(copy.deepcopy(view.swagger_responses))
    if not responses:
        responses = default_response(verb)
    responses = {
        str(key): value
        for key, value in responses.items()
        }
    return responses


def swagger(app):
    paths = defaultdict(dict)
    definitions = defaultdict(dict)

    for rule in app.url_map.iter_rules():
        endpoint = app.view_functions[rule.endpoint]
        api_view_map = _group_endpoints_by_http_verb(endpoint, rule.methods)
        operations = dict()
        for verb, view in api_view_map.items():
            summary, description, swag = _parse_docstring(view)
            if swag is None:
                continue

            _complete_tags(swag, view)
            _complete_security(swag, view)

            schema_ns = view.__module__ + view.__name__

            params = swag.get('parameters', [])
            _complete_params(params, view, rule)

            responses = _complete_responses(
                swag.get('responses', {}), view, verb)

            defs = _extract_definitions(
                swag.get('definitions', []), namespace=schema_ns)

            defs += _extract_definitions(params, namespace=schema_ns)
            defs += _extract_definitions(responses.values(), namespace=schema_ns)

            for definition in defs:
                # swagger definition without id
                def_id = definition.pop('id')
                # extract id definition
                if def_id is not None:
                    definitions[':'.join([schema_ns, def_id])].update(definition)

            operation = {
                'summary': summary,
                'description': description,
                'responses': responses,
                'parameters': params
            }

            # other optionals
            for key in _optional_fields:
                if key in swag:
                    operation[key] = swag.get(key)
            operations[verb] = operation

        if len(operations):
            path = str(rule)
            for arg in re.findall('(<([^<>]*:)?([^<>]*)>)', path):
                path = path.replace(arg[0], '{%s}' % arg[2])
            paths[path].update(operations)
    return {
        'paths': paths,
        'definitions': definitions,
        "swagger": "2.0",
        "info": {
            "version": "0.0.1",
            "title": "swagger project",
        }
    }
