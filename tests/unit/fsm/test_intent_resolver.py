from app.fsm.intent_resolver import Intent, IntentResolver


def test_intent_resolver_detects_add_product_from_noisy_text() -> None:
    resolver = IntentResolver()

    assert resolver.resolve("hey, I need to add a product please") is Intent.ADD_PRODUCT


def test_intent_resolver_detects_record_sale() -> None:
    resolver = IntentResolver()

    assert resolver.resolve("record sale") is Intent.RECORD_SALE
    assert resolver.resolve("add a new sale") is Intent.RECORD_SALE


def test_intent_resolver_detects_generate_report() -> None:
    resolver = IntentResolver()

    assert resolver.resolve("generate report") is Intent.GENERATE_REPORT
    assert resolver.resolve("send daily report please") is Intent.GENERATE_REPORT
    assert resolver.resolve("nataka ripoti") is Intent.GENERATE_REPORT


def test_intent_resolver_detects_unknown_for_unrelated_text() -> None:
    resolver = IntentResolver()

    assert resolver.resolve("what's the weather today?") is Intent.UNKNOWN
