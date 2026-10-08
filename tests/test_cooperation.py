"""真实编排轨迹、异步实战及基于持久化证据的学习推荐。模型边界使用替身。"""
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents.base import AgentResult
from brain_of_cloud.services.agents.concierge import AgentResponse
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def make_orchestrator(tmp_path):
    store = SQLiteStore(tmp_path / 'trace.sqlite')
    store.initialize()
    return Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=MagicMock()), store


def test_dispatch_changes_and_parallel_hat_timing(tmp_path):
    orch, _ = make_orchestrator(tmp_path)
    events = []
    orch._concierge.think = MagicMock(side_effect=[
        AgentResponse(tool_calls=[{'id':'q1','name':'quiz_user','arguments':{'random_mode':'explicit'}}]),
        AgentResponse(tool_calls=[{'id':'r1','name':'review_material','arguments':{'content':'学习内容'}}]),
        AgentResponse(text='请作答。'),
    ])
    for name in ['white','black','green','yellow','red']:
        getattr(orch, f'_{name}_hat').run = MagicMock(return_value=AgentResult(content='审查意见', passed=True))
    orch._blue_hat.coordinate = MagicMock(return_value='合格')
    orch.handle_user_message('u', 's', '出几道题考考我', trace_cb=events.append)
    decisions = [event for event in events if event.get('event') == 'dispatch']
    # 出题后程序直接交付答题卡，本次实际发生两轮分工。
    assert [len(event['agents']) for event in decisions] == [1, 6]
    assert decisions[0]['agents'] == ['training_analyzer']
    starts = [i for i,e in enumerate(events) if e['agent'] in {'white_hat','black_hat','green_hat','yellow_hat','red_hat'} and e['status']=='working']
    ends = [i for i,e in enumerate(events) if e['agent'].endswith('_hat') and e['agent']!='blue_hat' and e['status']=='done']
    blue_start = next(i for i,e in enumerate(events) if e['agent']=='blue_hat' and e['status']=='working')
    assert len(starts) == len(ends) == 5
    assert max(starts) < min(ends) < max(ends) < blue_start
    assert events[-1]['step'] == 'delivery'


def test_concierge_can_reply_without_calling_other_roles(tmp_path):
    orch, _ = make_orchestrator(tmp_path)
    orch._concierge.think = MagicMock(return_value=AgentResponse(text='你好，欢迎开始学习。'))
    events = []
    orch.handle_user_message('u', 's', '你好', trace_cb=events.append)
    decisions = [event for event in events if event.get('event') == 'dispatch']
    assert len(decisions) == 1 and decisions[0]['agents'] == []
    assert events[-1]['step'] == 'delivery'


def wait_task(client, task_id):
    for _ in range(120):
        task = client.get(f'/tasks/{task_id}').json()
        if task['status'] in ('completed','failed'):
            assert task['status']=='completed', task['error']
            return task
        time.sleep(.02)
    raise AssertionError('任务超时')


def mock_client(tmp_path):
    llm = MagicMock()
    llm.generate.return_value = SimpleNamespace(content=json.dumps({'reply':'您好，我们逐项确认。','mood':'一般','advanced':False,'trust_delta':3,'total':85,'dims':{'表达能力':4}},ensure_ascii=False))
    return TestClient(create_app(db_path=tmp_path/'api.sqlite',llm_client=llm,use_real_knowledge=False))


def test_catalog_and_async_communication_flow(tmp_path):
    client = mock_client(tmp_path)
    catalog = client.get('/agents/catalog').json()
    ids = {item['id'] for item in catalog['agents']}
    assert len(ids) == catalog['active_count'] == 17
    assert not ids.intersection(catalog['reserved'])
    scenes = client.get('/sandbox/templates',params={'mode':'communication'}).json()['templates']
    assert {s['template_id'] for s in scenes} == {'t_comm_phone','t_comm_wechat'}
    with patch('brain_of_cloud.services.customer_generator.CustomerGenerator.generate', return_value={'name':'Emma','nationality':'英国','age':'32','personality':'耐心','preferences':'文化','quirks':'简短','hidden':'有饮食需求'}):
        result = client.post('/sandbox/tasks/start',json={'user_id':'u','template_id':'t_comm_wechat'}).json()
        start = wait_task(client,result['task_id'])
    sid = start['payload']['session_id']
    assert any(e['agent']=='customer_generator' and e['status']=='working' for e in start['trace'])
    assert start['trace'][-1]['step']=='delivery'
    with patch('brain_of_cloud.services.scene_director.SceneDirectorAgent.decide',return_value=SimpleNamespace(action='continue',reason='继续确认需求')):
        result = client.post(f'/sandbox/sessions/{sid}/messages/tasks',json={'user_id':'u','content':'请问您的时间安排？'}).json()
        message = wait_task(client,result['task_id'])
    assert message['payload']['reply']
    assert any(e['agent']=='scene_director' and e['status']=='done' for e in message['trace'])
    assert client.post(f'/sandbox/sessions/{sid}/end/tasks',json={'user_id':'other'}).status_code==403
    assert client.post('/sandbox/sessions/missing/end/tasks',json={'user_id':'u'}).status_code==404
    result = client.post(f'/sandbox/sessions/{sid}/end/tasks',json={'user_id':'u'}).json()
    end = wait_task(client,result['task_id'])
    assert end['payload']['status']=='ended'
    assert any(e['agent']=='sandbox_evaluator' for e in end['trace'])
    status = client.get('/learning/status',params={'user_id':'u','session_id':'s'}).json()
    assert status['practice_count'] == status['specialty_count'] == 1
    assert status['integrated_count'] == 0


def test_learning_recommendation_tracks_mastery_and_reteach(tmp_path):
    client = mock_client(tmp_path)
    db = SQLiteStore(tmp_path/'api.sqlite')
    state = {'session_id':'s','user_id':'u','topic_ids':['kp_1'],'stage':'practicing','depth':'intro','quiz_history':['q1'],'consecutive_correct':0,'consecutive_incorrect':0,'last_quiz':None,'topic_finished':False}
    db.save_teaching_state('s','u',state)
    with patch('brain_of_cloud.services.mastery.MasteryService.skill_mastery',return_value={'mastery':82}):
        value = client.get('/learning/status',params={'user_id':'u','session_id':'s'}).json()
        assert value['recommendation']['path']=='/app/training?focus=integrated'
        state['reteach_question_id']='q1'
        db.save_teaching_state('s','u',state)
        value = client.get('/learning/status',params={'user_id':'u','session_id':'s'}).json()
        assert '错因' in value['recommendation']['label']
    assert client.get('/learning/status',params={'user_id':'other','session_id':'s'}).status_code==403
