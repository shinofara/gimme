# -*- coding: utf-8 -*-
#
# Copyright 2018 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Fixtures."""
from __future__ import absolute_import, print_function, unicode_literals

import time

import pytest
from freezegun import freeze_time

from gimme.app import create_app
from gimme.settings import Testing


@pytest.fixture
def app():
    """Creates an app fixture with the testing configuration."""
    app = create_app(config_object=Testing)
    yield app


@pytest.fixture
def loggedin_app(app):
    """Creates a logged-in test client instance.

    This instance passes all the requiremnets we check for so it
    results in a functional and logged in application.
    """
    with freeze_time('2018-05-04', tz_offset=0):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['domain'] = 'example.com'
                sess['account'] = 'test@example.com'
                sess['google_oauth_token'] = {
                    'access_token': 'this is not real',
                    'id_token': 'and neither is this',
                    'token_type': 'Bearer',
                    'expires_in': '3600',
                    'expires_at': time.time() + 3600,
                }
            yield client


@pytest.fixture
def invalid_loggedin_app(app):
    """Creates an invalid logged in test client instane.

    This client comes from a non-whitelisted domain and as such
    should cause the application to deny access.
    """
    with freeze_time('2018-05-04', tz_offset=0):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['domain'] = 'example.org'
                sess['account'] = 'test@example.org'
                sess['google_oauth_token'] = {
                    'access_token': 'this is not real',
                    'id_token': 'and neither is this',
                    'token_type': 'Bearer',
                    'expires_in': '3600',
                    'expires_at': time.time() + 3600,
                }
            yield client


@pytest.fixture
def incomplete_loggedin_app(app):
    """Creates a logged-in test client instance without profile info.

    This instance has a valid OAuth session but no profile infromation yet.
    It should cause the application to attempt to fetch the profile info
    and store it in the session.
    """
    with freeze_time('2018-05-04', tz_offset=0):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['google_oauth_token'] = {
                    'access_token': 'this is not real',
                    'id_token': 'and neither is this',
                    'token_type': 'Bearer',
                    'expires_in': '3600',
                    'expires_at': time.time() + 3600,
                }
            yield client
