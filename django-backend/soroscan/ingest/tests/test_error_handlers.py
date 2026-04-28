"""
Tests for custom error handlers.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestErrorHandlers:
    def test_404_returns_json(self):
        """Test that 404 errors return JSON instead of HTML."""
        client = Client()
        response = client.get('/nonexistent-endpoint/')
        
        assert response.status_code == 404
        assert response['Content-Type'] == 'application/json'
        
        data = response.json()
        assert data['error'] == 'Not Found'
        assert data['status_code'] == 404
        assert 'message' in data

    def test_404_response_structure(self):
        """Test that 404 response has the correct JSON structure."""
        client = Client()
        response = client.get('/api/nonexistent-path/')
        
        assert response.status_code == 404
        data = response.json()
        
        assert isinstance(data, dict)
        assert 'error' in data
        assert 'status_code' in data
        assert 'message' in data
        assert data['status_code'] == 404
