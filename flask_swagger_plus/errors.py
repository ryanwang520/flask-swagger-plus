#!/usr/bin/env python
# -*- coding: utf-8 -*-


class FlaskSwaggerError(Exception):
    pass


class ValidationError(FlaskSwaggerError):
    pass
