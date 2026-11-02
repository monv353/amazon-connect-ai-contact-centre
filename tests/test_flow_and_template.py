"""Static checks that the contact flow, the Lex bot and the template agree with each other."""

import json
import re
from pathlib import Path

import pytest
from cfnlint.decode import cfn_yaml

import render_template

ROOT = Path(__file__).resolve().parent.parent
FLOW_PATH = ROOT / "connect" / "flows" / "inbound-flow.json"
TEMPLATE_PATH = ROOT / "infra" / "template.yaml"

FAKE_VALUES = {
    "LexBotAliasArn": "arn:aws:lex:ap-southeast-1:111122223333:bot-alias/BOTID12345/ALIAS12345",
    "SupportQueueArn": "arn:aws:connect:ap-southeast-1:111122223333:instance/abc/queue/def",
}


@pytest.fixture(scope="module")
def flow():
    return json.loads(FLOW_PATH.read_text())


@pytest.fixture(scope="module")
def template():
    return cfn_yaml.load(str(TEMPLATE_PATH))


def lex_intents(template):
    locale = template["Resources"]["LexBot"]["Properties"]["BotLocales"][0]
    return {intent["Name"] for intent in locale["Intents"]}


def test_flow_has_valid_structure(flow):
    assert flow["Version"] == "2019-10-30"
    ids = [a["Identifier"] for a in flow["Actions"]]
    assert len(ids) == len(set(ids)), "duplicate action identifiers"
    assert flow["StartAction"] in ids
    assert len(ids) <= 250


def test_every_transition_points_to_an_existing_action(flow):
    ids = {a["Identifier"] for a in flow["Actions"]}
    for action in flow["Actions"]:
        t = action.get("Transitions", {})
        targets = [t.get("NextAction")] if t.get("NextAction") else []
        targets += [c["NextAction"] for c in t.get("Conditions", [])]
        targets += [e["NextAction"] for e in t.get("Errors", [])]
        for target in targets:
            assert target in ids, f"{action['Identifier']} -> unknown action {target}"


def test_every_action_is_reachable(flow):
    by_id = {a["Identifier"]: a for a in flow["Actions"]}
    seen, todo = set(), [flow["StartAction"]]
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        t = by_id[current].get("Transitions", {})
        todo += [t["NextAction"]] if t.get("NextAction") else []
        todo += [c["NextAction"] for c in t.get("Conditions", [])]
        todo += [e["NextAction"] for e in t.get("Errors", [])]
    assert seen == set(by_id), f"unreachable: {set(by_id) - seen}"


def test_metadata_positions_cover_all_actions(flow):
    assert set(flow["Metadata"]["ActionMetadata"]) == {a["Identifier"] for a in flow["Actions"]}


def test_lex_branches_match_bot_intents(flow, template):
    intents = lex_intents(template)
    assert {"CheckBalance", "ReportOutage", "TalkToAgent", "FallbackIntent"} <= intents
    lex_blocks = [a for a in flow["Actions"] if a["Type"] == "ConnectParticipantWithLexBot"]
    assert lex_blocks
    for block in lex_blocks:
        branched = {c["Condition"]["Operands"][0] for c in block["Transitions"]["Conditions"]}
        assert branched == intents, f"{block['Identifier']} branches {branched} but bot has {intents}"
        assert block["Parameters"]["LexV2Bot"]["AliasArn"] == "${LexBotAliasArn}"


def test_lambda_handles_every_bot_intent(template):
    import handler
    assert lex_intents(template) <= set(handler.HANDLERS)


def test_contact_lens_enabled_for_chat_and_voice(flow):
    rec = next(a for a in flow["Actions"] if a["Type"] == "UpdateContactRecordingBehavior")
    analytics = rec["Parameters"]["AnalyticsBehavior"]
    assert analytics["Enabled"] == "True"
    assert analytics["ChannelConfiguration"]["Chat"]["AnalyticsModes"] == ["ContactLens"]
    assert analytics["ChannelConfiguration"]["Voice"]["AnalyticsModes"] == ["RealTime"]
    # Analytics requires both participants to be recorded.
    assert set(rec["Parameters"]["RecordingBehavior"]["RecordedParticipants"]) == {"Agent", "Customer"}


def test_flow_placeholders_match_sub_variables(template):
    content = template["Resources"]["InboundFlow"]["Properties"]["Content"]["Fn::Sub"]
    assert content[0] == "__INBOUND_FLOW_JSON__"
    variables = set(re.findall(r"\$\{([A-Za-z0-9]+)\}", FLOW_PATH.read_text()))
    assert variables == set(content[1]) == set(FAKE_VALUES)


def test_rendered_template_contains_parseable_flow(tmp_path):
    out = tmp_path / "template.yaml"
    out.write_text(render_template.render(TEMPLATE_PATH.read_text(), FLOW_PATH.read_text()))
    rendered = cfn_yaml.load(str(out))
    body = rendered["Resources"]["InboundFlow"]["Properties"]["Content"]["Fn::Sub"][0]
    for name, value in FAKE_VALUES.items():
        body = body.replace("${" + name + "}", value)
    assert "${" not in body
    parsed = json.loads(body)
    assert parsed == json.loads(
        FLOW_PATH.read_text().replace("${LexBotAliasArn}", FAKE_VALUES["LexBotAliasArn"])
        .replace("${SupportQueueArn}", FAKE_VALUES["SupportQueueArn"])
    )
    assert len(body) < 256_000
