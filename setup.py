# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='django-sda_donation_tracker',
    version='2.1',
    author='Games Done Quick',
    author_email='tracker@gamesdonequick.com',
    packages=['sda_donation_tracker'],
    url='https://github.com/uraniumanchor/sda-donation-tracker-2',
    license='GPLv2',
    description='A Django app to assist in tracking donations for live broadcast events.',
    long_description=open('README.rst').read(),
    zip_safe=False,
    include_package_data=True,
    package_data={'': ['README.rst']},
    install_requires=[
        'chromium-compact-language-detector',
        'Django>=1.8',
        'django-post-office',
        'django-ajax-selects',
        'django-mptt',
        'gdata',
        'oauth2client',
        'psycopg2',
        'python-dateutil',
        'pytz',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Other Audience',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
