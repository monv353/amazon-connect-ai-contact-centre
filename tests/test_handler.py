"""Unit tests for the Lex V2 fulfillment Lambda. Bedrock is replaced by a fake client."""

import pytest

import handler


class FakeBedrock:
    """Records converse() calls and returns a canned answer (or raises)."""

    def __init__(self, text="Bills are due on the 20th of each month.", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {
            "output": {"message": {"role": "assistant", "content": [{"text": self.text}]}},
            "usage": {"inputTokens": 900, "outputTokens": 20},
        }


@pytest.fixture
def fake_bedrock(monkeypatch):
    fake = FakeBedrock()
    monkeypatch.setattr(handler, "_bedrock_client", fake)
    return fake


def lex_event(intent, slots=None, transcript="", attributes=None):
    """Minimal Lex V2 code hook event, shaped like the real payload."""
    return {
        "sessionId": "session-123",
        "inputTranscript": transcript,
        "invocationSource": "FulfillmentCodeHook",
        "bot": {"id": "BOTID12345", "aliasId": "ALIAS12345", "localeId": "en_US", "version": "1"},
        "sessionState": {
            "sessionAttributes": attributes or {},
            "intent": {"name": intent, "slots": slots or {}, "state": "ReadyForFulfillment",
                       "confirmationState": "None"},
        },
    }


def slot(value, resolved=None):
    return {"value": {"originalValue": value, "interpretedValue": value,
                      "resolvedValues": resolved if resolved is not None else [value]}}


def message(response):
    return response["messages"][0]["content"]


def assert_closed(response):
    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["intent"]["state"] == "Fulfilled"
    assert response["messages"][0]["contentType"] == "PlainText"


# --- CheckBalance -------------------------------------------------------------

def test_check_balance_unpaid_account():
    resp = handler.lambda_handler(lex_event("CheckBalance", {"AccountNumber": slot("10012345")}))
    assert_closed(resp)
    assert "IDR 150,000" in message(resp)
    assert "20 November" in message(resp)
    assert resp["sessionState"]["sessionAttributes"]["accountStatus"] == "unpaid"


def test_check_balance_strips_spaces_and_dashes():
    resp = handler.lambda_handler(lex_event("CheckBalance", {"AccountNumber": slot("1006-7890")}))
    assert "overdue" in message(resp)
    assert "late fee" in message(resp)


def test_check_balance_paid_account():
    resp = handler.lambda_handler(lex_event("CheckBalance", {"AccountNumber": slot("10024680")}))
    assert "fully paid" in message(resp)


def test_check_balance_unknown_account_sets_flag():
    resp = handler.lambda_handler(lex_event("CheckBalance", {"AccountNumber": slot("99999999")}))
    assert_closed(resp)
    assert resp["sessionState"]["sessionAttributes"]["accountFound"] == "false"
    assert "couldn't find" in message(resp)


def test_check_balance_keeps_existing_session_attributes():
    event = lex_event("CheckBalance", {"AccountNumber": slot("10012345")}, attributes={"channel": "CHAT"})
    resp = handler.lambda_handler(event)
    assert resp["sessionState"]["sessionAttributes"]["channel"] == "CHAT"


# --- ReportOutage -------------------------------------------------------------

def test_report_outage_known_outage():
    slots = {"ServiceType": slot("home fiber", ["Home Fiber"]), "ServiceArea": slot("jaksel", ["Jakarta Selatan"])}
    resp = handler.lambda_handler(lex_event("ReportOutage", slots))
    assert_closed(resp)
    attrs = resp["sessionState"]["sessionAttributes"]
    assert attrs["knownOutage"] == "true"
    assert attrs["ticketId"].startswith("INC-")
    assert "18:00 WIB" in message(resp)


def test_report_outage_unknown_opens_ticket_with_troubleshooting():
    slots = {"ServiceType": slot("Home Fiber"), "ServiceArea": slot("Bandung")}
    resp = handler.lambda_handler(lex_event("ReportOutage", slots))
    assert resp["sessionState"]["sessionAttributes"]["knownOutage"] == "false"
    assert "PON light" in message(resp)


def test_ticket_id_is_deterministic_per_session():
    a = handler.ticket_id("s1", "bandung", "mobile")
    assert a == handler.ticket_id("s1", "bandung", "mobile")
    assert a != handler.ticket_id("s2", "bandung", "mobile")


# --- TalkToAgent / Goodbye ----------------------------------------------------

def test_talk_to_agent_sets_escalate():
    resp = handler.lambda_handler(lex_event("TalkToAgent"))
    assert_closed(resp)
    assert resp["sessionState"]["sessionAttributes"]["escalate"] == "true"
    assert resp["sessionState"]["intent"]["name"] == "TalkToAgent"


def test_goodbye():
    resp = handler.lambda_handler(lex_event("Goodbye"))
    assert "Terima kasih" in message(resp)


# --- FallbackIntent -> Bedrock FAQ ---------------------------------------------

def test_fallback_answers_from_bedrock(fake_bedrock):
    resp = handler.lambda_handler(lex_event("FallbackIntent", transcript="When is my bill due?"))
    assert_closed(resp)
    assert message(resp) == "Bills are due on the 20th of each month."
    assert resp["sessionState"]["sessionAttributes"]["faqAnswered"] == "true"

    call = fake_bedrock.calls[0]
    assert call["modelId"] == handler.MODEL_ID
    assert call["messages"][0]["content"][0]["text"] == "When is my bill due?"
    # The grounding document is in the system prompt, not the user turn.
    system_text = call["system"][0]["text"]
    assert "Arunika Telecom customer FAQ" in system_text
    assert "{knowledge}" not in system_text
    assert call["inferenceConfig"]["temperature"] <= 0.2


def test_fallback_no_answer_escalates(fake_bedrock):
    fake_bedrock.text = "NO_ANSWER"
    resp = handler.lambda_handler(lex_event("FallbackIntent", transcript="Can I pay with bitcoin?"))
    assert resp["sessionState"]["sessionAttributes"]["faqAnswered"] == "false"
    assert "agent" in message(resp)


def test_fallback_bedrock_error_escalates_instead_of_failing(fake_bedrock):
    fake_bedrock.error = RuntimeError("ThrottlingException")
    resp = handler.lambda_handler(lex_event("FallbackIntent", transcript="What plans do you have?"))
    assert_closed(resp)
    assert resp["sessionState"]["sessionAttributes"]["faqAnswered"] == "false"


def test_fallback_empty_transcript_skips_bedrock(fake_bedrock):
    resp = handler.lambda_handler(lex_event("FallbackIntent", transcript="   "))
    assert fake_bedrock.calls == []
    assert resp["sessionState"]["sessionAttributes"]["faqAnswered"] == "false"


def test_fallback_truncates_long_questions(fake_bedrock):
    handler.lambda_handler(lex_event("FallbackIntent", transcript="x" * 5000))
    assert len(fake_bedrock.calls[0]["messages"][0]["content"][0]["text"]) == 500


def test_unknown_intent_is_treated_as_fallback(fake_bedrock):
    resp = handler.lambda_handler(lex_event("SomethingNew", transcript="Berapa harga Home Fiber 50 Mbps?"))
    assert resp["sessionState"]["sessionAttributes"]["faqAnswered"] == "true"
    assert len(fake_bedrock.calls) == 1


def test_mask_hides_account_number():
    assert handler.mask("10012345") == "*****345"
