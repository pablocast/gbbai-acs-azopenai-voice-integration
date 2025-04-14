import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from quart import Quart
from src.core.app import CallAutomationApp
from requests import status_codes


@pytest_asyncio.fixture
async def app():
    """Fixture to provide the Quart app instance."""
    app_instance = CallAutomationApp().app
    yield app_instance


@pytest_asyncio.fixture
async def client(app):
    """Fixture to provide the Quart test client."""
    async with app.test_client() as test_client:
        yield test_client

# HAPPY PATH  - INITIATE OUTBOUND CALL

# successful call initiation 
@pytest.mark.asyncio
async def test_initiate_outbound_call_success(client, mocker):
    # ARRANGE
    # mock request_get_json
    mock_request_json = mocker.patch("quart.request.get_json")
    mock_request_json.return_value = {
        "phone_number": "+12345567890", 
        "additional_data": {
            "Name": "John Doe"
        }
    }
    
    # mock call_automation_client.create_call()
    mock_call_result = mocker.MagicMock()
    mock_call_result.call_connection_id = "12345"
    mock_acs_create_call = mocker.patch("azure.communication.callautomation.CallAutomationClient.create_call")
    mock_acs_create_call.return_value = mock_call_result
    
    # mock cosmos db service
    mock_cosmos_create_new_session = mocker.patch("src.services.cosmosdb_service.CosmosDBService.create_new_session")
    mock_cosmos_create_new_session.return_value = "cosmos-session-id"
    
    # mock redis cache servie
    mock_cache_set = mocker.patch("src.services.cache_service.CacheService.set")
        
    # ACT
    response = await client.post("/api/initiateOutboundCall", json={
        "phone_number": "+12345567890",
        "additional_data": {
            "Name": "John Doe"
        }
    })
    
    # ASSERT
    assert response.status_code == status_codes.codes.ok
    mock_acs_create_call.assert_called_once()
    mock_cosmos_create_new_session.assert_called_with(
        caller_id = mock_request_json.return_value["phone_number"],
        acs_connection_id = mock_call_result.call_connection_id
    )
    
    assert mock_cache_set.call_count == 5
    
    
    
    
    