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
"""Helpers."""
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import requests
import urllib
import urlparse
import os
from datetime import timedelta, tzinfo
from functools import wraps

from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from flask import (current_app, flash, redirect, render_template, session,
                   url_for)
from validators import url
from google.oauth2 import service_account
import googleapiclient.discovery
CLOUD_RM = 'https://cloudresourcemanager.googleapis.com/v1/projects'
ZERO = timedelta(0)


def project_from_field(value):
    """Get the project ID from the form field.

    If the supplied value appears to be a URL, try to parse the project ID
    out of it and return that. Otherwise return the empty string.

    When it doesn't look like a URL assume it's not and return the value.

    To be on the safe side, URL encode the result to avoid being vulnerable
    to clever people.
    """
    if url(value):
        qs = dict(urlparse.parse_qsl(urlparse.urlparse(value).query))
        if 'project' in qs:
            return urllib.quote_plus(qs['project'])
        return ''
    else:
        return urllib.quote_plus(value)


def check_valid_domain(domain, valid_domains):
    """Check if the logged-in user comes from a valid domain."""
    if domain in valid_domains:
        return True
    return False

def login_required(google):
    """Enforces authentication on a route."""
    def decorated(func):
        @wraps(func)
        def decorated_route(*args, **kwargs):
            if not google.authorized:
                return redirect(url_for('google.login'))

            if not all(key in session for key in ['domain', 'account']):
                resp = google.get('/userinfo/v2/me')
                if resp.status_code != 200:
                    flash('Could not get your profile information from Google',
                          'error')
                    return render_template('sorry.html.j2'), 403
                body = resp.json()
                if not all(v in body.keys() for v in ['hd', 'email']):
                    flash(('Incomplete profile information was returned by '
                           'Google'), 'error')
                    return render_template('sorry.html.j2'), 403
                session['domain'] = body['hd']
                session['account'] = body['email']

            if check_valid_domain(
                session['domain'],
                current_app.config.get('ALLOWED_GSUITE_DOMAINS', []),
            ):
                return func(*args, **kwargs)
            flash(('The account you are logged in with does not match the '
                   'configured whitelist'), 'error')
            return render_template('sorry.html.j2'), 403
        return decorated_route
    return decorated

class UTC(tzinfo):
    """A tzinfo class representing UTC."""

    def utcoffset(self, dt):
        """Returns this timezone's offset from UTC."""
        return ZERO

    def tzname(self, dt):
        """Human friendly timezone name."""
        return 'UTC'

    def dst(self, dt):
        """Returns the daylight savings time offset for UTC."""
        return ZERO


utc = UTC()


def add_conditional_binding(google, form):
    """Add a new conditional binding to a project."""
    project = project_from_field(form.project.data)
    if project == '':
        flash('Could not find project ID in provided URL', 'error')
        return
    set_condition(google, form, project, 'user')

def get_policy(project_id, version=3):
    """Gets IAM policy for a project."""

    credentials = service_account.Credentials.from_service_account_file(
        filename=os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    service = googleapiclient.discovery.build(
        "cloudresourcemanager", "v1", credentials=credentials
    )
    policy = (
        service.projects()
        .getIamPolicy(
            resource=project_id,
            body={"options": {"requestedPolicyVersion": version}},
        )
        .execute()
    )
    return policy


def set_policy(project_id, policy):
    """Sets IAM policy for a project."""

    credentials = service_account.Credentials.from_service_account_file(
        filename=os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    service = googleapiclient.discovery.build(
        "cloudresourcemanager", "v1", credentials=credentials
    )

    policy = (
        service.projects()
        .setIamPolicy(resource=project_id, body={"policy": policy})
        .execute()
    )

    return policy


def set_condition(google, form, project, user_or_group):
    expiry = (datetime.datetime.now(utc) + datetime.timedelta(
        minutes=form.period.data)).isoformat()
    
    new_policy = {'policy': get_policy(project)}

    new_policy['policy']['bindings'].append(
        {'condition': {
            'expression': 'request.time < timestamp("{}")'.format(expiry),
            'description': 'This is a temporary grant created by Gimme',
            'title': 'granted by {}'.format(session['account'])},
        'members': ['{}:{}@{}'.format(user_or_group, form.target.data,
                                        form.domain.data)],
        'role': form.access.data})

    new_policy['policy']['version'] = 3

    try:
        set_policy(project, new_policy['policy'])
    except (OAuth2Error, requests.HTTPError):
        flash('Could not apply new policy: {}'.format(
            result.json()['error']['message']), 'error')
        return
    flash("Great success, they'll have access in a minute!", 'success')
    return
