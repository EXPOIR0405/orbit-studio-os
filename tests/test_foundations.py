import pytest
from fastapi.testclient import TestClient
from orbit.api import app
from orbit import service, storage as db
from orbit.routing import route
from orbit.tools import ToolBox
from orbit.memory import search_approved
from orbit.evaluation import evaluate
from orbit.models import Report
from test_missions import mission, complete

def test_routes_are_bounded_and_explained():
    assert route('원고 설정만 검토')['roles']==['pd','story','qa']
    assert route('홍보 문안 작성')['roles']==['pd','audience','campaign','qa']
    assert route('전체 공개 준비')['workflow']=='full'
    with pytest.raises(ValueError):
        route('anything','shell')

def test_live_disabled_even_with_key(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-not-a-real-key')
    monkeypatch.setenv('ORBIT_ENABLE_LIVE','false')
    with TestClient(app) as c:
        assert not c.get('/health').json()['live_configured']
        assert c.post('/missions',json={'title':'live','goal':'실제 호출 차단 확인','mode':'live'}).status_code==403

def test_tool_allowlist_and_data_scope():
    log=[]
    box=ToolBox('audience',[{'id':'R01','text':'합성 독자 반응'}],'test',1,log.append)
    assert box.call('search_sources',{'query':'합성'})[0]['id']=='R01'
    for name,args in [('execute_sql',{'query':'delete'}),('get_source',{'source_id':'S06'}),('search_approved_memory',{'query':''})]:
        with pytest.raises(ValueError):
            box.call(name,args)
    assert len(log)==4
    assert all(x['status']=='denied_or_invalid' for x in log[1:])

def test_invalid_evidence_rejected():
    report=Report(summary='검토',draft='초안',needs_review=False,findings=[{'title':'문제','detail':'내용','sources':['FOREIGN'],'severity':'info'}])
    result=evaluate('story',report,[{'id':'S04'}])
    assert not result['passed'] and not result['gates']['references_in_scope']

def test_memory_only_approved_and_version_scoped():
    with TestClient(app) as c:
        m=complete(c,mission(c))
        assert m['id'] not in [x['mission_id'] for x in search_approved('',1,'none',limit=100)]
        c.post(f"/missions/{m['id']}/approvals",json={'version':m['version'],'package_hash':m['package_hash']})
        assert m['id'] in [x['mission_id'] for x in search_approved('',1,'none',limit=100)]
        assert search_approved('',999,'none',limit=100)==[]

def test_trace_and_evaluation_saved_for_each_role():
    with TestClient(app) as c:
        m=complete(c,mission(c))
        assert len(m['traces'])==5
        for t in m['traces']:
            assert t['reason'] and t['duration_ms']>=0
            assert t['tools'] and t['evaluation']['passed']
            assert t['requests'][0]['status']=='completed'
        assert all(u['estimated_cost_usd']==0 for u in m['usage'])

def test_selective_route_runs_only_requested_roles():
    with TestClient(app) as c:
        m=c.post('/missions',json={'title':'story','goal':'원고 설정 검토','workflow':'story'}).json()
        m=complete(c,m)
        assert set(m['artifacts'])=={'pd','story','qa'}
        assert m['calls']==3
        assert c.post(f"/missions/{m['id']}/revisions",json={'version':1,'role':'campaign','instruction':'잘못된 역할 요청'}).status_code==409

def test_live_provider_guard_precedes_client(monkeypatch):
    from orbit import provider
    monkeypatch.setenv('ORBIT_ENABLE_LIVE','false')
    monkeypatch.setattr(provider,'OpenAI',lambda **kw: pytest.fail('network client must not be constructed'))
    with pytest.raises(ValueError):
        provider.generate('pd',{},'live',None,None,None)

def test_qa_quote_must_exist_in_target_artifact():
    artifacts={'campaign':{'summary':'문안','draft':'1. 일요일 저녁,\n별빛식당의 온기','findings':[]}}
    def qa(quote,target='campaign',severity='blocker'):
        report=Report(summary='검수',draft='체크',needs_review=True,findings=[{'title':'스포일러','detail':'d','sources':['S06'],'severity':severity,'target':target,'quote':quote}])
        return evaluate('qa',report,[{'id':'S06'}],artifacts)
    assert qa('일요일 저녁, 별빛식당의 온기')['passed']
    hallucinated=qa('마지막 손님은 스승이었다')
    assert not hallucinated['gates']['qa_quotes_verified'] and hallucinated['unverified_quotes']==['스포일러']
    assert not qa('일요일 저녁',target='story')['passed']
    assert qa('',severity='info')['passed']

def test_story_without_conflicts_passes_but_audience_needs_evidence():
    empty=Report(summary='충돌 없음',draft='수정 필요 없음',needs_review=False,findings=[])
    assert evaluate('story',empty,[{'id':'S01'}])['passed']
    assert not evaluate('audience',empty,[{'id':'R01'}])['gates']['analysis_has_evidence']

def test_campaign_quote_must_come_from_copy_not_notes():
    artifacts={'campaign':{'summary':'','draft':'1. 바다와 등대의 EP.8','findings':[{'title':'요청 미반영','detail':"'전 세계 1위' 요청은 근거가 없어 제외",'sources':['B-P01'],'severity':'warning'}]}}
    report=Report(summary='검수',draft='체크',needs_review=True,findings=[{'title':'근거 없는 순위','detail':'d','sources':['B-P01'],'severity':'blocker','target':'campaign','quote':'전 세계 1위'}])
    assert not evaluate('qa',report,[{'id':'B-P01'}],artifacts)['gates']['qa_quotes_verified']
