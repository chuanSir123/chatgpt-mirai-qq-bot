import pytest
import json
import asyncio
from im_http_legacy_adapter.adapter import HttpLegacyAdapter, HttpLegacyConfig, ResponseResult

@pytest.fixture
def config():
    return HttpLegacyConfig(
        host="127.0.0.1",
        port=8080,
        debug=False
    )

@pytest.fixture
def adapter(config):
    return HttpLegacyAdapter(config)

@pytest.mark.asyncio
async def test_chat_endpoint(adapter):
    test_client = adapter.app.test_client()
    
    # Test text message
    response = await test_client.post('/v1/chat', json={
        'session_id': 'test_session',
        'username': 'test_user',
        'message': 'Hello, world!'
    })
    
    assert response.status_code == 200
    data = json.loads(await response.get_data())
    assert 'result' in data
    assert 'message' in data
    assert isinstance(data['message'], list)

    # Test with missing fields (should use defaults)
    response = await test_client.post('/v1/chat', json={
        'message': 'Test message'
    })
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_response_result():
    # Test single message
    result = ResponseResult(message="Test message")
    json_data = json.loads(result.to_json())
    assert json_data['message'] == ["Test message"]
    assert json_data['voice'] == []
    assert json_data['image'] == []
    
    # Test multiple messages
    result = ResponseResult(
        message=["Message 1", "Message 2"],
        voice=["voice1.mp3"],
        image=["image1.jpg", "image2.jpg"]
    )
    json_data = json.loads(result.to_json())
    assert len(json_data['message']) == 2
    assert len(json_data['voice']) == 1
    assert len(json_data['image']) == 2

@pytest.mark.asyncio
async def test_adapter_lifecycle(adapter):
    # Test start and stop
    start_task = asyncio.create_task(adapter.start())
    await asyncio.sleep(0.1)  # Give some time for server to start
    await adapter.stop()
    try:
        await start_task
    except Exception:
        pass  # Expected to fail when we stop the server
