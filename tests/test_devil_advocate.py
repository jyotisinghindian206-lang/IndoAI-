from indo_devil_advocate import enabled, build_guidance


def test_disabled_by_default():
    assert not enabled("What do you think of my idea?", "New Chat")
    assert build_guidance("Hello", "New Chat") == ""


def test_explicit_mode():
    assert enabled("Review my proposal", "Devil's Advocate")
    assert "strongest reasonable counterargument" in build_guidance("Review my proposal", "Devil's Advocate")


def test_explicit_turn_request():
    assert enabled("Play devil's advocate and challenge my plan")
    assert enabled("Stress-test this architecture")


def test_no_false_trigger_on_unrelated_text():
    assert not enabled("I watched a movie about a devil", "New Chat")
