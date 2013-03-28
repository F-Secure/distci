"""
Test DistCI frontend build artifact handling

Copyright (c) 2013 Heikki Nousiainen, F-Secure
See LICENSE for details
"""

from nose.plugins.skip import SkipTest
from webtest import TestApp, TestRequest
import json
import tempfile
import os
import shutil
import threading
import urllib2
import wsgiref.simple_server

import frontend

class BackgroundHttpServer:
    def __init__(self, server):
        self.server = server
        self.running = True

    def serve(self):
        while True:
            if self.running == False:
                break
            self.server.handle_request()

class SilentWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    def log_message(self, *args):
        pass

class TestJobsBuildArtifacts:
    app = None
    config_file = None
    data_directory = None
    test_state = {}

    @classmethod
    def setUpClass(cls):
        cls.data_directory = tempfile.mkdtemp()
        os.mkdir(os.path.join(cls.data_directory, 'jobs'))
        os.mkdir(os.path.join(cls.data_directory, 'tasks'))

        config = { "data_directory": cls.data_directory,
                   "task_frontends": ['http://localhost:9988/'] }

        cls.frontend_app = frontend.Frontend(config)
        cls.app = TestApp(cls.frontend_app.handle_request)

        cls.server = wsgiref.simple_server.make_server('localhost', 9988, cls.frontend_app.handle_request, handler_class=SilentWSGIRequestHandler)
        cls.slave = BackgroundHttpServer(cls.server)
        cls.slave_thread = threading.Thread(target=cls.slave.serve)
        cls.slave_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.slave.running = False
        r = urllib2.urlopen('http://localhost:9988/')
        _ = r.read()
        cls.slave_thread.join()
        cls.app = None
        shutil.rmtree(cls.data_directory)

    def test_00_setup(self):
        test_job_data_file = os.path.join(os.path.dirname(__file__), 'test-frontend-jobs-builds_job-config.json')
        test_job_data = json.load(file(test_job_data_file, 'rb'))
        request = TestRequest.blank('/jobs', content_type='application/json')
        request.method = 'POST'
        request.body = json.dumps(test_job_data)
        response = self.app.do_request(request, 201, False)
        result = json.loads(response.body)
        assert result.has_key('job_id'), "ID entry went missing"
        assert result.has_key('config'), "config entry went missing"
        self.test_state['job_id'] = str(result['job_id'])

        request = TestRequest.blank('/jobs/%s/builds' % self.test_state['job_id'])
        request.method = 'POST'
        response = self.app.do_request(request, 201, False)
        result = json.loads(response.body)
        assert result.has_key('job_id'), "ID entry went missing"
        assert result.has_key('build_number'), "build_number went missing"
        self.test_state['build_number'] = str(result['build_number'])

    def test_01_create_artifact(self):
        request = TestRequest.blank('/jobs/%s/builds/%s/artifacts' % (self.test_state['job_id'], self.test_state['build_number']), content_type='application/octet-stream')
        request.method = 'POST'
        request.body = 'test_content'
        response = self.app.do_request(request, 201, False)
        result = json.loads(response.body)
        assert result.has_key('job_id'), "ID entry went missing"
        assert result.has_key('build_number'), "build_number went missing"
        assert result.has_key('artifact_id'), "Artifact ID went missing"
        self.test_state['artifact_id'] = str(result['artifact_id'])

    def test_02_get_artifact(self):
        response = self.app.request('/jobs/%s/builds/%s/artifacts/%s' % (self.test_state['job_id'], self.test_state['build_number'], self.test_state['artifact_id']))
        assert response.body == 'test_content', "Wrong data"

    def test_03_update_artifact(self):
        request = TestRequest.blank('/jobs/%s/builds/%s/artifacts/%s' % (self.test_state['job_id'], self.test_state['build_number'], self.test_state['artifact_id']), content_type='application/octet-stream')
        request.method = 'PUT'
        request.body = 'test_content_modified'
        response = self.app.do_request(request, 200, False)
        result = json.loads(response.body)
        assert result.has_key('job_id'), "ID entry went missing"
        assert result.has_key('build_number'), "build_number went missing"
        assert result.has_key('artifact_id'), "Artifact ID went missing"
        assert result['artifact_id'] == self.test_state['artifact_id'], "Artifact ID mismatch"

        response = self.app.request('/jobs/%s/builds/%s/artifacts/%s' % (self.test_state['job_id'], self.test_state['build_number'], self.test_state['artifact_id']))
        assert response.body == 'test_content_modified', "Wrong data"

    def test_04_delete_artifact(self):
        request = TestRequest.blank('/jobs/%s/builds/%s/artifacts/%s' % (self.test_state['job_id'], self.test_state['build_number'], self.test_state['artifact_id']), content_type='application/octet-stream')
        request.method = 'DELETE'
        _ = self.app.do_request(request, 204, False)

