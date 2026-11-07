from indo_hyperlocal import HyperLocalIntelligence, infer_language
import pytest


def test_language_detection_hinglish_and_hindi():
    assert infer_language('bhai kya haal hai') == 'hinglish'
    assert infer_language('नमस्ते') == 'hindi'
    assert infer_language('Hello there') == 'english'


def test_location_is_opt_in_and_account_scoped(tmp_path):
    engine = HyperLocalIntelligence(tmp_path)
    engine.update('a', {'enabled': True, 'city': 'Gurugram', 'region': 'Haryana', 'language': 'hinglish'})
    assert 'Gurugram' in engine.context('a', 'hello')
    assert 'Gurugram' not in engine.context('b', 'hello')
    assert 'disabled' in engine.context('b', 'hello')


def test_rejects_precise_or_address_like_location(tmp_path):
    engine = HyperLocalIntelligence(tmp_path)
    with pytest.raises(ValueError):
        engine.update('a', {'enabled': True, 'city': 'Sector 12, House 42'})
    with pytest.raises(ValueError):
        engine.update('a', {'enabled': True, 'city': '28.4595, 77.0266'})


def test_language_override_and_secondary_languages(tmp_path):
    engine = HyperLocalIntelligence(tmp_path)
    profile = engine.update('a', {'enabled': True, 'language': 'tamil', 'secondary_languages': ['hindi', 'english']})
    assert profile['language'] == 'tamil'
    assert profile['secondary_languages'] == ['hindi', 'english']
    with pytest.raises(ValueError):
        engine.update('a', {'language': 'not-a-language'})


def test_unknown_timezone_is_rejected(tmp_path):
    engine = HyperLocalIntelligence(tmp_path)
    with pytest.raises(ValueError, match="Unknown IANA"):
        engine.update("acct-a", {"timezone": "Mars/Olympus_Mons"})
