from app.fsm.intent_resolver import Intent, IntentResolver


def test_intent_resolver_detects_add_product_from_noisy_text() -> None:
    resolver = IntentResolver()

    assert resolver.resolve("hey, I need to add a product please") is Intent.ADD_PRODUCT


def test_intent_resolver_detects_unknown_for_unrelated_text() -> None:
    resolver = IntentResolver()

    assert resolver.resolve("what's the weather today?") is Intent.UNKNOWN
