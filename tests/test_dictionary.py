from unittest.mock import AsyncMock, patch

def test_dictionary_success(client):
    with patch("app.routers.dictionary.get_word_definition", new_callable=AsyncMock) as mock_dict:
        mock_dict.return_value = {"word": "hello", "definition": "test"}
        res = client.get("/api/dictionary?word=hello")
        assert res.status_code == 200

def test_dictionary_error(client):
    with patch("app.routers.dictionary.get_word_definition", new_callable=AsyncMock) as mock_dict:
        mock_dict.side_effect = Exception("API down")
        res = client.get("/api/dictionary?word=hello")
        assert res.status_code == 503