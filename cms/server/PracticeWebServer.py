#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Luca Versari <veluca93@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import io
import re
import json
import logging
import mimetypes
import pkg_resources
from datetime import datetime

from cms import config
from cms.io import WebService
from cms.db.filecacher import FileCacher
from cms.db import Session, User, Contest

from werkzeug.wrappers import Response, Request
from werkzeug.wsgi import SharedDataMiddleware, DispatcherMiddleware, \
    wrap_file, responder
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound, BadRequest


logger = logging.getLogger(__name__)


class CheckHandler(object):
    def __init__(self, session, contest):
        self.session = session
        self.contest = contest
        self.mailreg = re.compile(r"[^@]+@[^@]+\.[^@]+")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    @responder
    def wsgi_app(self, environ, start_response):
        request = Request(environ)

        if request.mimetype != "application/json":
            return BadRequest()
        try:
            req = json.load(request.stream)
        except ValueError:
            return BadRequest()

        resp = dict()
        if req["type"] == "username":
            if len(req["value"]) < 4:
                resp["success"] = 0
                resp["error"] = "Username troppo corto"
            else:
                user = self.session.query(User)\
                    .filter(User.contest == self.contest)\
                    .filter(User.username == req["value"]).first()
                if user is None:
                    resp["success"] = 1
                else:
                    resp["success"] = 0
                    resp["error"] = "Username gia' esistente"

        elif req["type"] == "email":
            if not self.mailreg.match(req["value"]):
                resp["success"] = 0
                resp["error"] = "Indirizzo email non valido"
            else:
                user = self.session.query(User)\
                    .filter(User.contest == self.contest)\
                    .filter(User.email == req["value"]).first()
                if user is None:
                    resp["success"] = 1
                else:
                    resp["success"] = 0
                    resp["error"] = "Email gia' esistente"

        response = Response()
        response.mimetype = "application/json"
        response.status_code = 200
        response.data = json.dumps(resp)

        return response


class FileHandler(object):
    def __init__(self, filename):
        self.filename = filename

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    @responder
    def wsgi_app(self, environ, start_response):
        path = os.path.join(
            pkg_resources.resource_filename("cms.web", "practice"),
            self.filename)

        response = Response()
        response.status_code = 200
        response.mimetype = "application/octect-stream"
        mimetype = mimetypes.guess_type(self.filename)[0]
        if mimetype is not None:
            response.mimetype = mimetype
        response.last_modified = \
            datetime.utcfromtimestamp(os.path.getmtime(path))\
                    .replace(microsecond=0)
        response.response = wrap_file(environ, io.open(path, 'rb'))
        response.direct_passthrough = True
        return response


class DBFileHandler(object):
    def __init__(self, file_cacher):
        self.file_cacher = file_cacher
        self.router = Map([
            Rule("/<digest>", methods=["GET"], endpoint="get"),
            Rule("/<digest>/<filename>", methods=["GET"], endpoint="get")
        ], encoding_errors="strict")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    @responder
    def wsgi_app(self, environ, start_response):
        route = self.router.bind_to_environ(environ)

        try:
            endpoint, args = route.match()
        except HTTPException as exc:
            return exc(environ, start_response)

        try:
            if endpoint == "get":
                return self.get(args, environ)
        except HTTPException as exc:
            return exc

        return NotFound()

    def get(self, args, environ):
        try:
            fobj = self.file_cacher.get_file(args["digest"])
        except KeyError:
            raise NotFound()

        response = Response()
        response.status_code = 200

        response.mimetype = "application/octect-stream"
        if "filename" in args:
            response.headers.add_header(
                b'Content-Disposition', b'attachment',
                filename=args["filename"])
            mimetype = mimetypes.guess_type(args['filename'])[0]
            if mimetype is not None:
                response.mimetype = mimetype

        response.response = wrap_file(environ, fobj)
        response.direct_passthrough = True
        return response


class RoutingHandler(object):
    def __init__(self):
        self.router = Map([
            Rule("/", methods=["GET"], endpoint="root"),
        ], encoding_errors="strict")

        self.root_handler = FileHandler("index.html")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        route = self.router.bind_to_environ(environ)
        try:
            endpoint, args = route.match()
        except HTTPException as exc:
            return exc(environ, start_response)

        if endpoint == "root":
            return self.root_handler(environ, start_response)

        return NotFound()


class PracticeWebServer(WebService):
    """Service that runs the web server for practice.

    """
    def __init__(self, shard, contest):
        self.contest = contest

        WebService.__init__(
            self,
            config.contest_listen_port[shard],
            [],
            {},
            shard=shard,
            listen_address=config.contest_listen_address[shard])

        self.file_cacher = FileCacher(self)
        self.session = Session()
        self.contest = Contest.get_from_id(contest, self.session)

        self.wsgi_app = SharedDataMiddleware(RoutingHandler(), {
            '/':        ("cms.web", "practice"),
            '/assets':  ("cms.web", "assets")
        })

        self.wsgi_app = DispatcherMiddleware(self.wsgi_app, {
            '/files':   DBFileHandler(self.file_cacher),
            '/check':   CheckHandler(self.session, self.contest)
        })
