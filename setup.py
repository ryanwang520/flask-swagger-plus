import os

from setuptools import setup

from flask_swagger_plus import __version__


readme = open('README.md').read()

CLASSIFIERS = [
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Topic :: Utilities',
    'Topic :: Software Development :: Libraries :: Python Modules',
]

fname = os.path.join(os.path.dirname(__file__), 'requirements.txt')

py_modules = []

for root, folders, files in os.walk('flask_swagger_plus'):
    for f in files:
        if f.endswith('.py'):
            full = os.path.join(root, f[:-3])
            parts = full.split(os.path.sep)
            modname = '.'.join(parts)
            py_modules.append(modname)

setup(
    name='flask-swagger-plus',
    version=__version__,

    url='http://github.com/moonshadow/flask-swagger-plus/',
    description='extract swagger spec from source code and docstring for a flask app',
    long_description=readme,
    author='Wang Haowei',
    author_email='hwwangwang@gmail.com',
    license='MIT',

    classifiers=CLASSIFIERS,
    zip_safe=False,
    py_modules=py_modules,
    include_package_data=True,
    install_requires=[
        'flask>=0.10',
        'PyYAML>=3.11',
        'marshmallow>=2.10.5'
    ],
)