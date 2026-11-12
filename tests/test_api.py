from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def valid_answers():
    questions = client.get('/api/questionnaire').json()['questions']
    return {q['key']: q['options'][0]['value'] for q in questions}

def test_health_and_questions():
    assert client.get('/health').status_code == 200
    result = client.get('/api/questionnaire').json()
    assert result['version'] == 2
    assert len(result['questions']) == 27

def test_analyze():
    response = client.post('/api/analyze', json={'answers': valid_answers()})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['analysis']['palette']) == 6
    assert data['answers']['_questionnaire_version'] == 2

def test_invalid_answer():
    assert client.post('/api/analyze', json={'answers': {'foo': 'bar'}}).status_code == 422

def test_products_and_translator():
    catalog = client.get('/api/products')
    assert catalog.status_code == 200
    assert catalog.json()['products']
    pid = catalog.json()['products'][0]['id']
    assert client.get('/api/translator', params={'product_id': pid}).status_code == 200

def test_advisor():
    response = client.post('/api/advisor', json={
        'occasion': 'universidad', 'budget': 150000,
        'answers': valid_answers(), 'owned_ids': []
    })
    assert response.status_code == 200, response.text
    assert response.json()['items']
