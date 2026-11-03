import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.acquisition.adapters import FileDatasetAdapter, MetaAuthorizedAdapter, ProviderDatasetAdapter, TikTokCreativeCenterAdapter, parse_meta, registry_gate
from app.acquisition.benchmark import benchmark, expansion, export_import, product_links, safe_value
from app.acquisition.contracts import Access, AcquisitionError, Page, Query, Record, utcnow
from app.acquisition.transport import Transport
from app.data_import import ImportOptions, create_preview, process_job, start_import
from app.models import RawEvidence, Source

SAMPLE = Path(__file__).with_name('acquisition') / 'sample.json'
QUERY = Query(keyword='solar garden lights')


def fixture_access():
    return Access(source_id='demo', source_name='Fixture', mode='FIXTURE_TEST', corpus_type='demo', authorization_status='FIXTURE_ONLY', countries=['US'], filters=['keyword','country'])


def live(**changes):
    return Access.model_validate(dict(source_id='meta-ad-library', source_name='Meta test only', mode='AUTHORIZED_PUBLIC_SOURCE', corpus_type='paid_ad', enabled=True, authorization_status='APPROVED', rights_reference='Synthetic isolated test approval only', countries=['US'], filters=['keyword','country']) | changes)


def test_fixture_metrics_and_core_import(client, session, tmp_path):
    adapter = FileDatasetAdapter(fixture_access(), SAMPLE, dataset_query=QUERY)
    result = benchmark(adapter, QUERY, tmp_path/'fixture.json', lambda a,q: registry_gate(session,a,q))
    metrics = result['summary']
    assert metrics['returned_count'] == 3 and metrics['unique_ad_count'] == 2
    assert metrics['duplicate_rate'] == pytest.approx(1/3)
    assert metrics['media_url_coverage'] == pytest.approx(1/3)
    assert metrics['advertiser_id_coverage'] == pytest.approx(2/3)
    assert metrics['synthetic'] and metrics['actual_cost'] is None
    exported = export_import(result)
    assert exported['fixture_only'] and len(exported['records']) == 2
    payload = json.dumps(exported).encode()
    job = create_preview(session,payload,'fixture.json',ImportOptions(source_id='demo',dataset_id='acquisition-fixture',data_label='DEMO',corpus='demo'))
    start_import(session,job['id'])
    process_job(job['id'],sessionmaker(bind=session.bind))
    rows = client.get('/ads?data_mode=demo&q=Synthetic%20solar&country=US&platform=meta').json()['items']
    assert rows and rows[0]['is_demo']
    ad_id = rows[0]['id']
    evidence = client.get(f'/ads/{ad_id}/evidence?data_mode=demo').json()['items']
    assert evidence[0]['raw_data']['_acquisition']['mode'] == 'FIXTURE_TEST'
    assert client.get(f'/ads/{ad_id}?data_mode=real').status_code == 404
    raw = session.scalar(select(RawEvidence).where(RawEvidence.job_id == job['id']))
    assert raw.is_demo and raw.raw_data['_acquisition']['scope_hash'] == result['scope_hash']
    with pytest.raises(ValueError,match='fixtures'):
        create_preview(session,payload,'fake-real.json',ImportOptions(permission_attested=True,rights_reference='Synthetic isolated test only'))


@pytest.mark.parametrize('changes,error', [({'enabled':False},'needs_approval'),({'authorization_status':'DENIED'},'needs_approval'),({'countries':['DE']},'unsupported_country'),({'filters':[]},'unsupported_filter'),({'paid':True,'budget_approved':True,'hard_budget_usd':1},'paid_execution_disabled_requires_vendor_enforced_budget')])
def test_preflight_no_network(changes,error,tmp_path):
    class Never:
        def get(self,*args,**kwargs):
            pytest.fail('Unauthorized network')
    result = benchmark(MetaAuthorizedAdapter(live(**changes),transport=Never()),QUERY,tmp_path/'blocked.json')
    assert result['error_type'] == error and result['summary']['returned_count'] is None
    assert result['summary']['duplicate_rate'] is None


def test_registry_cannot_be_bypassed(session,tmp_path):
    path=tmp_path/'denied.json'
    result=benchmark(MetaAuthorizedAdapter(live()),QUERY,path,lambda a,q:registry_gate(session,a,q))
    assert result['error_type']=='registry_denied' and result['authorization_status']=='DENIED'
    with pytest.raises(AcquisitionError,match='terminal_run'):
        benchmark(MetaAuthorizedAdapter(live()),QUERY,path,resume=True)


@pytest.mark.parametrize('status,expected,calls',[(403,'access_denied',1),(302,'redirect_denied',1),(429,'rate_limited',3),(500,'upstream_unavailable',3)])
def test_transport_retry(status,expected,calls):
    observed,delays=[],[]
    def handler(request):
        observed.append(request)
        return httpx.Response(status,headers={'Retry-After':'1'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AcquisitionError,match=expected):
            Transport('api.apify.com',client,delays.append).get('https://api.apify.com/v2/datasets/test/items')
    assert len(observed)==calls and len(delays)==calls-1


def test_transport_host_size_schema_and_retry_after():
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(429,headers={'Retry-After':'99'}))) as client:
        transport=Transport('api.apify.com',client)
        for url in ('http://api.apify.com/x','https://localhost/x','https://user:password@api.apify.com/x','https://api.apify.com:444/x'):
            with pytest.raises(AcquisitionError,match='endpoint_not_allowed'):
                transport.get(url)
        with pytest.raises(AcquisitionError,match='retry_after_exceeds'):
            transport.get('https://api.apify.com/x')
    for body,expected in [(b'x','invalid_json'),(b'x'*(2*1024*1024+1),'response_too_large')]:
        with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=body))) as client:
            with pytest.raises(AcquisitionError,match=expected):
                Transport('api.apify.com',client).get('https://api.apify.com/x')


def test_meta_mapping_unknowns():
    row=parse_meta({'id':'123','page_id':'456','publisher_platforms':['facebook','instagram']},utcnow())
    assert row.platform=='meta' and row.country is None and row.status=='unknown'
    assert not row.media_urls and row.started_at is None and row.landing_url is None and row.ad_copy is None


def test_public_partial_and_challenge():
    class Public:
        def get(self,*args,**kwargs):
            return '<script type="application/json">'+json.dumps({'collated_results':[{'ad_archive_id':'1','page_id':'2','page_name':'Fixture','is_active':True,'snapshot':{'body':{'text':'Synthetic copy'}}}]})+'</script>'
    page=MetaAuthorizedAdapter(live(),transport=Public()).collect_page(QUERY)
    assert page.completeness=='partial' and page.records[0].ad_id=='1' and page.records[0].country is None
    class Challenge:
        def get(self,*args,**kwargs):
            return '<form id="login_form"></form>'
    with pytest.raises(AcquisitionError,match='access_challenge'):
        MetaAuthorizedAdapter(live(),transport=Challenge()).collect_page(QUERY)


def test_official_cursor_host_and_token(monkeypatch):
    monkeypatch.setenv('META_ACCESS_TOKEN','test-only-secret')
    calls=[]
    class Official:
        def get(self,url,params,headers):
            calls.append((url,params,headers))
            return {'data':[{'id':'1'}],'paging':{'next':'https://evil.example/?access_token=secret','cursors':{'after':'opaque'}}}
    page=MetaAuthorizedAdapter(live(mode='OFFICIAL_API'),version='v99.0',transport=Official()).collect_page(QUERY,'prior')
    assert page.next_checkpoint=='opaque' and calls[0][1]['after']=='prior'
    assert calls[0][0]=='https://graph.facebook.com/v99.0/ads_archive' and 'access_token' not in calls[0][1]


def test_tiktok_disabled():
    with pytest.raises(AcquisitionError,match='needs_approved_creative_center_transport'):
        TikTokCreativeCenterAdapter(live(source_id='tiktok-creative-center',corpus_type='curated_top_ad')).collect_page(QUERY)


def test_provider_existing_dataset_only(monkeypatch):
    monkeypatch.setenv('APIFY_TOKEN','test-only')
    calls=[]
    class Provider:
        def get(self,url,params,headers):
            calls.append((url,params))
            return [{'id':'fixture','copy':'Synthetic copy'}]
    adapter=ProviderDatasetAdapter(live(mode='LICENSED_PROVIDER'),'test_dataset',QUERY,{'ad_id':'id','ad_copy':'copy'},Provider())
    page=adapter.collect_page(QUERY)
    assert page.records[0].ad_copy=='Synthetic copy' and page.records[0].country is None
    assert calls[0][0].endswith('/v2/datasets/test_dataset/items')
    with pytest.raises(AcquisitionError,match='dataset_query_mismatch'):
        adapter.collect_page(Query(keyword='different'))
    assert len(calls)==1


def test_csv_mapping_and_partition(tmp_path):
    file=tmp_path/'sample.csv'
    file.write_text('MyId,Seen,fixture_only\nfixture-1,2026-11-01T00:00:00Z,true\n')
    adapter=FileDatasetAdapter(fixture_access(),file,{'external_id':'MyId','observed_at':'Seen'},QUERY)
    assert adapter.collect_page(QUERY).records[0].ad_id=='fixture-1'
    adapter.access=live(mode='AUTHORIZED_IMPORT')
    with pytest.raises(AcquisitionError,match='fixture_partition_mismatch'):
        adapter.collect_page(QUERY)


def test_checkpoint_resume_and_loop(tmp_path):
    class Paged:
        access=fixture_access()
        def collect_page(self,query,checkpoint):
            return Page(records=[Record(ad_id=str(checkpoint or 'start'),observed_at=utcnow())],next_checkpoint='next' if checkpoint is None else None)
    path=tmp_path/'pages.json'
    first=benchmark(Paged(),QUERY,path,max_pages=1)
    assert first['completeness']=='capped' and first['next_checkpoint']=='next'
    resumed=benchmark(Paged(),QUERY,path,resume=True)
    assert len(resumed['records'])==2 and resumed['pages_received']==2
    with pytest.raises(AcquisitionError,match='checkpoint_scope_mismatch'):
        benchmark(Paged(),Query(keyword='changed'),path,resume=True)
    class Loop(Paged):
        def collect_page(self,query,checkpoint):
            return Page(records=[],next_checkpoint='repeat')
    result=benchmark(Loop(),QUERY,tmp_path/'loop.json')
    assert result['error_type']=='repeated_checkpoint' and result['pages_received']==2


def test_expansion_and_product_variants(tmp_path):
    class Expanded:
        access=fixture_access().model_copy(update={'filters':['keyword','country','advertiser']})
        def collect_page(self,query,checkpoint):
            return Page(records=[Record(ad_id='new',advertiser_id=query.advertiser_id,observed_at=utcnow()),Record(ad_id='base',advertiser_id=query.advertiser_id,observed_at=utcnow())])
    initial={'records':[Record(ad_id='base',advertiser_id='brand',observed_at=utcnow()).model_dump(mode='json')]}
    result=expansion(Expanded(),QUERY,initial,tmp_path/'expansion')
    assert result['additional_unique_ads']==1 and result['synthetic']
    links=product_links([{'ad_id':'1','landing_url':'https://example.com/products/light?variant=one'},{'ad_id':'2','landing_url':'https://example.com/products/light?variant=two'}])
    assert len(links)==2 and links[0]['domain']==links[1]['domain']


def test_redaction():
    value=safe_value({'access_token':'secret','url':'https://example.com/a?token=secret&variant=one'})
    assert 'secret' not in json.dumps(value) and 'variant=one' in value['url']


def test_registry_scope(session):
    source=session.get(Source,'meta-ad-library')
    source.approval_status,source.live_enabled,source.state='approved',True,'ready'
    session.commit()
    registry_gate(session,live(),QUERY)
    with pytest.raises(AcquisitionError,match='registry_denied'):
        registry_gate(session,live(corpus_type='curated_top_ad'),QUERY)


def test_file_checkpoint_binds_content_and_cap(tmp_path):
    file=tmp_path/'history.json'
    data=json.loads(SAMPLE.read_text())
    data['records']=data['records']*10
    file.write_text(json.dumps(data))
    adapter=FileDatasetAdapter(fixture_access(),file,dataset_query=QUERY)
    path=tmp_path/'state.json'
    first=benchmark(adapter,QUERY,path,max_pages=1)
    assert first['next_checkpoint']=='25' and len(first['records'])==25
    data['records'][0]['creative_text']='Modified fixture'
    file.write_text(json.dumps(data))
    with pytest.raises(AcquisitionError,match='checkpoint_scope_mismatch'):
        benchmark(adapter,QUERY,path,resume=True)
    capped=benchmark(adapter,QUERY.model_copy(update={'limit':1}),tmp_path/'cap.json')
    assert capped['completeness']=='capped' and len(capped['records'])==1


def test_missing_country_not_invented_on_export(tmp_path):
    class Unknown:
        access=fixture_access()
        def collect_page(self,query,checkpoint):
            return Page(records=[Record(ad_id='fixture',advertiser='Fixture',platform='meta',observed_at=utcnow())])
    result=benchmark(Unknown(),QUERY,tmp_path/'unknown.json')
    exported=export_import(result)
    assert not exported['records'] and exported['skipped'][0]['reason']=='missing_import_identity_or_declared_country'
    assert result['summary']['observed_country_coverage']==0


def test_unsupported_query_fields():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Query(keyword='test',industry='unverified_filter')


def test_source_scope_change_between_pages_stops(tmp_path):
    class Changed:
        access=fixture_access()
        version=1
        def checkpoint_identity(self):
            return self.version
        def collect_page(self,query,checkpoint):
            self.version=2
            return Page(records=[Record(ad_id='fixture',observed_at=utcnow())],next_checkpoint='next')
    result=benchmark(Changed(),QUERY,tmp_path/'changed.json')
    assert result['error_type']=='source_scope_changed_during_run' and result['pages_received']==1


def test_failed_expansion_is_not_zero_uplift(tmp_path):
    class Denied:
        access=fixture_access().model_copy(update={'filters':['keyword','country','advertiser']})
        def collect_page(self,query,checkpoint):
            raise AcquisitionError('access_denied')
    initial={'records':[Record(ad_id='base',advertiser_id='brand',observed_at=utcnow()).model_dump(mode='json')]}
    result=expansion(Denied(),QUERY,initial,tmp_path/'denied-expansion')
    assert result['status']=='blocked' and result['additional_unique_ads'] is None
