from unittest.mock import patch

@patch("app.services.dictionary_service.get_dictionary")
def test_dictionary_success(mock_dict, client):
    mock_dict.return_value = {
        "word": "hello",
        "definition": "test"
    }

    res = client.get("/api/dictionary?word=hello")

    assert res.status_code == 200


@patch("app.services.dictionary_service.get_dictionary")
def test_dictionary_error(mock_dict, client):
    mock_dict.side_effect = Exception("API down")
    res = client.get("/api/dictionary?word=hello")
    assert res.status_code in 200