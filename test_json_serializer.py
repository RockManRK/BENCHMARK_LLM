import json
from src.core.json_serializer import serialize_json


def test_none_returns_none():
    assert serialize_json(None) is None


def test_dict_pretty_true():
    data = {"name": "João", "age": 30}
    result = serialize_json(data, pretty=True)
    expected = json.dumps(data, indent=2, ensure_ascii=False)
    assert result == expected
    assert "  " in result  # Indentation present


def test_dict_pretty_false():
    data = {"name": "João", "age": 30}
    result = serialize_json(data, pretty=False)
    expected = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    assert result == expected
    assert "  " not in result  # No indentation


def test_string_input_returns_as_is():
    input_str = '{"already": "serialized"}'
    result = serialize_json(input_str)
    assert result is input_str  # Same object reference


def test_list_input():
    data = [1, "dois", {"três": 3}]
    result = serialize_json(data, pretty=True)
    expected = json.dumps(data, indent=2, ensure_ascii=False)
    assert result == expected


def test_other_types():
    assert serialize_json(42) == "42"
    assert serialize_json(3.14) == "3.14"
    assert serialize_json(True) == "true"
    assert serialize_json(False) == "false"


def test_unicode_preserved():
    data = {"mensagem": "Olá mundo! ãõç"}
    result = serialize_json(data, pretty=False)
    assert "Olá mundo! ãõç" in result
