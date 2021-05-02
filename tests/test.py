import pytest
import requests


async def test_client_set_value():
    resp = requests.post('http://127.0.0.1:8080/client', data={'name': 'test_post', 'password': 'test_pass'})
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_client_set_same_value():
    resp = requests.post('http://127.0.0.1:8080/client', data={'name': 'test_post', 'password': 'test_pass'})
    assert resp.status_code == 400
    assert resp.json()['success'] == False


async def test_client_get_value():
    resp = requests.get('http://127.0.0.1:8080/client')
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_client_put_value():
    resp = requests.put('http://127.0.0.1:8080/client', data={'name': 'test_put', 'password': 'test_pass', 'id': 1})
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_limit_set_value():
    resp = requests.post('http://127.0.0.1:8080/limits', data={'country': 'RUS', 'amount': 16000, 'cur': 'RUB', 'client_id': 1})
    assert resp.status_code == 400
    assert resp.json()['success'] == False


async def test_limit_get_value():
    resp = requests.get('http://127.0.0.1:8080/limits?id=1')
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_limit_put_value():
    resp = requests.put('http://127.0.0.1:8080/limits', data={'country': 'RUS', 'amount': 16000, 'cur': 'RUB', 'client_id': 1})
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_limit_delete_value():
    resp = requests.delete('http://127.0.0.1:8080/limits?id=1')
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_transfer_set_value():
    resp = requests.post('http://127.0.0.1:8080/transfer',
                          data={'country': 'RUS', 'amount': 14000, 'cur': 'RUB', 'client_id': 1})
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_limit_set_same_value():
    resp = requests.post('http://127.0.0.1:8080/limits', data={'country': 'RUS', 'amount': 14000, 'cur': 'RUB', 'client_id': 1})
    assert resp.status_code == 400
    assert resp.json()['success'] == False


async def test_transfer_set_big_value():
    resp = requests.post('http://127.0.0.1:8080/transfer', data={'country': 'RUS', 'amount': 1000000, 'cur': 'RUB', 'client_id': 1})
    assert resp.status_code == 406
    assert resp.json()['success'] == False


async def test_history_get_value():
    resp = requests.get('http://127.0.0.1:8080/history?id=1')
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_transfer_put_value():
    resp = requests.put('http://127.0.0.1:8080/transfer', data={'country': 'RUS', 'amount': 14000, 'cur': 'RUB', 'client_id': 1, 'id': 1})
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_history_delete_value():
    resp = requests.delete('http://127.0.0.1:8080/history?id=1')
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_client_delete_value():
    resp = requests.delete('http://127.0.0.1:8080/client?id=1')
    assert resp.status_code == 200
    assert resp.json()['success']


async def test_limit_get_empty_value():
    resp = requests.get('http://127.0.0.1:8080/limits?id=1')
    assert resp.status_code == 200
    assert resp.json()['success']
    assert resp.json()['data'] == []


async def test_history_get_empty_value():
    resp = requests.get('http://127.0.0.1:8080/history?id=1')
    assert resp.status_code == 200
    assert resp.json()['success']
    assert resp.json()['data'] == []

