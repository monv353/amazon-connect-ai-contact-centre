# Walkthrough (for Michael)

This explains every file and decision in plain language, so you can defend it in an interview, followed by likely questions and hands-on exercises.

## The story in one paragraph

A customer opens a chat (or calls). The Amazon Connect **contact flow** greets them, turns on **Contact Lens**, and hands the conversation to a **Lex V2 bot**. Lex works out what the customer wants (the *intent*) and collects any missing details (the *slots*, such as the account number). It then calls a **Lambda** function to fulfil the request. The Lambda answers bill and outage questions from mock data. If Lex doesn't recognise the question at all (`FallbackIntent`), the Lambda asks **Amazon Bedrock** to answer from a one-page FAQ, and only from that page. The bot then closes and returns to the flow, which branches: ask "anything else?", escalate to the **queue** for a human agent, or hang up. When an agent takes over, they see the chat history and the bot's notes. After the contact, Contact Lens shows sentiment, a summary and a redacted transcript.

## File by file

### `infra/template.yaml`: all the AWS resources

Read it top to bottom. It's grouped into four sections.

1. **Connect instance and storage**
   - `AWS::Connect::Instance` with `IdentityManagementType: CONNECT_MANAGED`, so users are stored inside Connect with no SAML or AD. `Attributes` turns features on at instance level: `ContactLens: true` lets flows use analytics, and `ContactflowLogs: true` sends flow logs to CloudWatch.
   - The instance does **not** create S3 storage when built through CloudFormation (the console does that for you). So the template creates an encrypted bucket and two `AWS::Connect::InstanceStorageConfig` resources, one for chat transcripts and one for call recordings. Contact Lens writes its output next to them.
   - `InstanceAlias` must be globally unique, because it becomes `https://<alias>.my.connect.aws`.
2. **Routing**
   - `HoursOfOperation` uses the `Asia/Jakarta` time zone. An `AgentHours` parameter switches between 24x7 (so a demo works at any time) and 08:00-22:00.
   - `Queue` is where waiting contacts sit until an agent is free.
   - `RoutingProfile` decides which queues an agent serves and how many contacts at once: 1 call, or 3 chats.
3. **Lambda and Bedrock permissions**
   - The Lambda role can write to its own log group and call `bedrock:InvokeModel` on one inference profile, plus the matching foundation model in any Region. Why "any Region"? A cross-Region inference profile may run your request in Tokyo, Sydney and so on, and IAM checks the model ARN in the Region that actually serves it.
   - The foundation model ID is derived from the profile ID with `Fn::Split`/`Fn::Select`. For example, `apac.amazon.nova-lite-v1:0` becomes `amazon.nova-lite-v1:0`.
   - `AWS::Lambda::Permission` lets `lexv2.amazonaws.com` call the function, but only from aliases of *this* bot (`SourceArn`).
4. **Lex bot, version, alias and association**
   - `AWS::Lex::Bot` holds the whole bot definition: locale `en_US`, voice, custom slot types (`ServiceArea`, `ServiceType`, with synonyms such as "Jaksel" for Jakarta Selatan) and 5 intents. `AutoBuildBotLocales: true` makes CloudFormation build the NLU model.
   - `FallbackIntent` is the built-in "I didn't understand" intent (`ParentIntentSignature: AMAZON.FallbackIntent`).
   - `AWS::Lex::BotVersion` freezes a numbered copy of the draft. `AWS::Lex::BotAlias` (`live`) points at that version and at the Lambda.
     - Gotcha: updating the bot does not publish a new version by itself. Rename the version's logical ID to force one.
   - `AWS::Connect::IntegrationAssociation` (`LEX_BOT`) lets the Connect instance use the bot alias, the same as "Add Lex bot" in the console. Connect also updates the alias's resource-based policy.
5. **Contact flow:** `AWS::Connect::ContactFlow` with `Content` set to the flow JSON. In the source template it's a placeholder, `"__INBOUND_FLOW_JSON__"`. `scripts/render_template.py` swaps in the real JSON. `Fn::Sub` then fills in `${LexBotAliasArn}` and `${SupportQueueArn}`.

### `connect/flows/inbound-flow.json`: the contact flow

This is Connect's "flow language". It's the same JSON the flow designer saves. Each block is an *Action* with an `Identifier`, a `Type`, `Parameters` and `Transitions` (next block, conditions, error branches).

| Action | Block in the designer | Why |
|---|---|---|
| `UpdateFlowLoggingBehavior` | Set logging behavior | Flow logs in CloudWatch for troubleshooting |
| `UpdateContactData` (LanguageCode en-US) | Set contact attributes / Set voice | A Lex V2 bot only works if the contact's language matches the bot locale |
| `UpdateContactRecordingBehavior` | Set recording and analytics behavior | Turns on Contact Lens: chat `ContactLens` mode, voice `RealTime`, redaction, sentiment, post-contact summary |
| `MessageParticipant` | Play prompt / Send message | Greeting and other messages |
| `ConnectParticipantWithLexBot` | Get customer input (Lex tab) | Runs the bot. Branches on the returned intent name with `Equals` conditions |
| `Compare` | Check contact attributes | Reads `$.Lex.SessionAttributes.faqAnswered` set by the Lambda |
| `UpdateContactAttributes` | Set contact attributes | Copies the bot's notes (`botLastIntent`, `botTicketId`, and so on) onto the contact so the agent sees them |
| `UpdateContactTargetQueue` | Set working queue | Chooses the Customer Care queue |
| `CheckHoursOfOperation` | Check hours of operation | `True` means in hours, `False` means after hours |
| `TransferContactToQueue` | Transfer to queue | Puts the contact in the queue, with an `QueueAtCapacity` error branch |
| `DisconnectParticipant` | Disconnect / hang up | End |

Design choice: **the bot closes after every intent**. The routing logic stays in the flow, where contact centre admins look for it, and the Lambda stays simple. Two Lex blocks are used: one with the first greeting, and an "anything else?" one that loops.

### `lambda/fulfillment/handler.py`: the brains

- `lambda_handler` looks up the intent name and dispatches to a handler. Unknown intents are treated as fallback.
- `handle_check_balance` reads the `AccountNumber` slot, strips non-digits and looks the number up in `ACCOUNTS` (the mock billing system). It returns different text for unpaid, overdue and paid accounts, and sets session attributes.
- `handle_report_outage` uses the resolved slot values (Lex turns "wifi" into "Home Fiber"). It checks `OUTAGES` and creates a deterministic ticket ID (a hash of the session, area and service, so tests are repeatable).
- `handle_fallback` sends the customer's text to Bedrock's **Converse API** with a system prompt containing the FAQ document and strict rules:
  - answer only from the document, in the customer's language, and in under 60 words;
  - if the answer isn't there, reply exactly `NO_ANSWER`.

  On `NO_ANSWER` or any error, it sets `faqAnswered=false` and the flow escalates. A model failure never strands a customer.
- `close()` builds the Lex V2 response: `dialogAction.type = Close`, intent state `Fulfilled`, a plain-text message, and the session attributes merged with the existing ones.
- `get_bedrock_client()` is lazy, so the tests can swap in a fake. It also sets short timeouts, because Lex won't wait forever.
- `mask()` keeps account numbers out of the logs (privacy by default).

### `lambda/fulfillment/knowledge/arunika_faq.md`

The grounding document. Changing what the bot knows is a document edit plus a redeploy. In production this becomes a Bedrock Knowledge Base (vector search over many documents).

### `scripts/`

- `deploy.sh` runs in this order:
  1. checks your identity;
  2. warns if the Bedrock profile isn't readable;
  3. creates an artifact bucket;
  4. zips the Lambda reproducibly, naming the file by content hash, so a code change gives a new S3 key and CloudFormation updates the function;
  5. renders the template;
  6. runs `aws cloudformation deploy`;
  7. creates `demo.agent` if `DEMO_AGENT_PASSWORD` is set. The password comes from the environment, never a file.
- `teardown.sh` asks you to type the stack name. It then empties the storage bucket (CloudFormation can't delete a non-empty bucket), deletes the stack, then deletes the artifact bucket.
- `render_template.py` checks that the flow JSON is valid, compacts it and inlines it.
- `verify.sh` runs all the offline checks.

### `tests/`

- `test_handler.py` covers each intent and the Bedrock paths (answer, `NO_ANSWER`, exception, empty input, long input), using a `FakeBedrock` class that records calls. It also checks that the grounding document goes into the *system* prompt, not the user turn, which is basic prompt-injection hygiene.
- `test_flow_and_template.py` checks that the pieces agree with each other:
  - every transition target exists, and every block is reachable;
  - the Lex branches equal the bot's intents;
  - the Lambda handles every intent;
  - Contact Lens is configured;
  - the flow placeholders equal the `Fn::Sub` variables;
  - the rendered template contains JSON that parses back to the original flow.

## Decisions you should be able to defend

1. **Singapore Region.** Connect isn't offered in Jakarta. Singapore has Connect, most Contact Lens features and Lex `en_US`, and it is closest to Indonesia.
2. **Nova Lite through the `apac.` profile.** It's not served in-Region in Singapore, and the APAC profile keeps inference in APAC Regions. Newer models are only offered globally from Singapore. It's cheap, fast and good enough for grounded answers.
3. **Generative AI on the fallback path only.** Money and outage answers are deterministic, and the LLM covers only the long tail.
4. **English locale.** `id_ID` in Lex has limited features, and Indonesian questions still get answered by Bedrock.
5. **Test chat instead of a phone number.** It's free to set up, avoids number regulation, and still shows Contact Lens.
6. **Plain CloudFormation, not CDK.** The JD's customers and Activeo's delivery teams read templates, and cfn-lint gives offline validation.

## Likely interview questions (with suggested answers)

1. **"Walk me through what happens when a customer types 'my wifi is down in Kemang'."**
   The flow's Get customer input sends the text to Lex. Lex matches `ReportOutage` from the `{ServiceType} is down in {ServiceArea}` utterance and resolves the synonyms. Both slots are filled, so it calls the Lambda for fulfillment. The Lambda finds the known outage and returns a Close with the ETA and a ticket ID in the session attributes. Connect branches on `ReportOutage` and asks "anything else?".

2. **"How do you stop the LLM from hallucinating?"**
   - It only runs when no intent matched.
   - The prompt restricts it to one approved document, with temperature 0.1.
   - It must say `NO_ANSWER` when unsure, which escalates to a human.
   - Errors also escalate.

   Next step: Bedrock Guardrails with a contextual grounding check, plus a golden test set of questions in CI.

3. **"Why is the Lex conversation closed after every intent instead of letting the bot keep talking?"**
   It keeps routing decisions in the Connect flow, where admins can see and change them, and it lets the flow react to bot results (escalate, loop, disconnect). The trade-off is one extra Lex block for the "anything else?" loop.

4. **"What does Contact Lens give you here, and what did you have to configure?"**
   Sentiment, a post-contact summary, redacted transcripts, and later categories, rules and evaluations. It needs the instance attribute `ContactLens`, a **Set recording and analytics behavior** block in the flow (chat `ContactLens`, voice `RealTime`), and S3 storage for output.

5. **"How would you price this for a 50-seat customer?"**
   Use the SOW cost model. On bundled pricing that's about USD 10.4k a month for 150k voice minutes and 400k chat messages. Per-feature pricing is about 17% cheaper on raw usage, but excludes WFM, QM and agent assist. The professional services are about 78 person-days plus contingency. Bedrock is a rounding error; per-minute charges and agent labour dominate.

6. **"A customer is on Cisco UCCE. How would you approach migration?"**
   Discovery first: ICM scripts, CVP apps, integrations, recording and WFM, and when contracts expire. Run coexistence with PSTN or SIP transfers, and migrate in phases by queue or channel, often starting with chat and AI self-service. Re-design the flows rather than converting scripts. Model per-minute cost against licences, SWSS and hardware.

7. **"What's the data residency story for an Indonesian bank?"**
   Connect, Lex and Contact Lens run in Singapore. Bedrock uses the APAC profile, so it stays in APAC Regions. PII is redacted in analytics and logs mask identifiers. Under UU PDP, cross-border transfer needs an equivalent level of protection or consent, so the customer's DPO must sign off. If voice must stay in-country, keep voice on-premises and put digital channels on Connect.

8. **"How do you get Indonesian phone numbers onto Connect?"**
   Connect doesn't sell Indonesian DIDs, and Indonesian toll-free was removed from coverage. Options are carrier forwarding to a Connect number, UIFN, or a partner carrier. I'd validate this in week 1 because carrier lead times are long.

9. **"How do you deploy changes to the bot safely?"**
   Change the bot in the template and publish a new version (rename the version's logical ID). The `live` alias moves to the new version, and rollback means pointing the alias back. Never use `TestBotAlias` in production because of its lower limits.

10. **"Why does the Lambda permission use a wildcard alias?"**
    So both the `live` alias and the console's `TestBotAlias` can call it. It's still scoped to this one bot ID in this account and Region.

11. **"What would you monitor in production?"**
    - Lambda errors and duration, and Bedrock throttles (CloudWatch alarms).
    - Lex missed-utterance analytics, and the `faqAnswered=false` rate as a content-gap signal.
    - Queue service level and abandonment, and Contact Lens sentiment trends.

12. **"What did you verify, and what couldn't you?"**
    Offline: cfn-lint against the current resource schemas, flow-graph tests, Lambda unit tests with a mocked Bedrock, and the packaging tested by unzipping and importing. A real deployment, the Connect test chat and Contact Lens output need an AWS account. The deploy script and demo script cover those steps.

## Try it yourself (exercises)

1. **Run the offline checks:** `./scripts/verify.sh`. Then break something on purpose: point a flow `NextAction` at a non-existent block, rerun the checks, and read which test fails and why.
2. **Add an intent:** add `UpgradePlan` to the bot (two utterances, no slots), a handler in `handler.py`, and a branch in both Lex blocks of the flow. Run the tests until they pass. They will tell you about each place you forgot.
3. **Change the knowledge:** add an FAQ entry about international roaming. In `test_handler.py`, assert the system prompt contains it.
4. **Deploy it:** with a sandbox account, `cp .env.example .env`, set `DEMO_AGENT_PASSWORD`, run `./scripts/deploy.sh`, and follow `docs/DEMO_SCRIPT.md`. Time the demo.
5. **Find the Contact Lens output:** after a chat, open the contact in Contact search. Then find the JSON in the S3 bucket under the Contact Lens analysis prefix.
6. **Swap the model:** redeploy with `BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0`. Compare the answers, and check the Lambda logs for token usage. Explain the residency trade-off out loud.
7. **Show after-hours:** redeploy with `AGENT_HOURS=BusinessHours` and chat after 22:00 WIB, or change the hours in the console.
8. **Open in the designer:** open the flow in Connect's flow designer and rearrange it. Use **Export flow** and diff the result against `connect/flows/inbound-flow.json`.
9. **Price a customer:** redo SOW section 5 for 20 agents and chat only. Which pricing option wins?
10. **Tear it down:** run `./scripts/teardown.sh`, and check the Billing console the next day.
