"""Offline tests of evidence attribution; no network or application data writes."""
import importlib.util
import io
from pathlib import Path
import socket
import ssl
from urllib.error import HTTPError, URLError

import pytest

spec = importlib.util.spec_from_file_location('acquisition_probes', Path(__file__).resolve().parents[3] / 'scripts/probe_acquisition_sources.py')
probes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probes)


@pytest.mark.parametrize('error,kind,status,proxy_status', [
    (URLError(OSError('Tunnel connection failed: 403 Forbidden')), 'proxy_connect_403', None, 403),
    (URLError(OSError('Tunnel connection failed: 407 Proxy Authentication Required')), 'proxy_authentication_failure', None, 407),
    (URLError(socket.gaierror(-2,'DNS failed')), 'dns_error', None, None),
    (URLError(ssl.SSLError('certificate failed')), 'tls_error', None, None),
    (TimeoutError('timeout'), 'timeout', None, None),
    (HTTPError('https://example.com',401,'denied',{},None), 'authentication_failure',401,None),
    (HTTPError('https://example.com',403,'denied',{},None), 'source_restriction_or_upstream_denial',403,None),
    (HTTPError('https://example.com',429,'limited',{},None), 'source_restriction_or_upstream_denial',429,None),
    (HTTPError('https://example.com',500,'failed',{},None), 'http_error',500,None),
])
def test_failure_layer_and_status(error,kind,status,proxy_status):
    def denied(*args,**kwargs):
        raise error
    result=probes.probe('test','https://example.com',denied)
    assert result['error_type']==kind and result['http_status']==status
    assert result['proxy_connect_status']==proxy_status
    assert result['duration_ms']>=0 and result['observed_at']
    if proxy_status:
        assert result['response_source']=='environment_proxy_connect'
    elif status:
        assert result['response_source']=='https_response_origin_unverified'


def test_success_is_not_proof_of_source_rights():
    class Response(io.BytesIO):
        status=200
        url='https://example.com'
    seen=[]
    def ok(request,timeout):
        seen.append((request.full_url,timeout))
        return Response(b'<html>shell only</html>')
    result=probes.probe('test','https://example.com',ok)
    assert seen==[('https://example.com',15)]
    assert result['http_status']==200 and result['error_type'] is None
    assert result['response_source']=='https_response_origin_unverified'
    assert result['sha256'] and result['bytes_read']==23
    assert 'approved' not in result


def test_exception_text_not_persisted():
    def fail(*args,**kwargs):
        raise URLError('failed https://example.com/?access_token=secret-value')
    result=probes.probe('test','https://example.com',fail)
    assert 'secret-value' not in str(result)
