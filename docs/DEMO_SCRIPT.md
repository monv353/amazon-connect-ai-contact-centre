# 10-minute pre-sales demo: Arunika Telecom AI contact centre

**Audience:** Head of Customer Care (business buyer), contact centre IT lead (technical evaluator), and possibly a risk or compliance representative.
**Goal:** Show that Amazon Connect can contain the top call drivers, answer long-tail questions safely with generative AI, and hand off to a human with full context, at pay-per-use cost.
**Setup:** Deploy with `scripts/deploy.sh`, `AGENT_HOURS=AlwaysOpen`. Use two browser windows side by side: the admin site with **Test chat** on the left, and the agent CCP (`/ccp-v2`, logged in as `demo.agent`, status **Available**) on the right. Open a third tab on **Analytics > Contact search** ahead of time.

## Personas

| Persona | Who | What they care about |
|---|---|---|
| **Budi** (customer) | Postpaid mobile customer, Jakarta, checks his bill on his phone | Fast answers, no repeating himself |
| **Siti** (customer) | Home Fiber customer whose internet just went down, slightly annoyed | Knowing when it will be fixed |
| **Dewi** (agent) | Customer care agent, 2 years in the job | Seeing what the bot already did, so she doesn't have to ask again |
| **Pak Hendra** (buyer) | Head of Customer Care | Containment, AHT, CSAT, and cost per contact |
| **Rina** (evaluator) | Contact centre IT lead | Integration effort, security, how hard it is to change |

## Run of show

| Time | Segment | What you do | What you say |
|---|---|---|---|
| 0:00-1:00 | **Frame** | Show the README architecture diagram | "Your top 3 contact drivers are bills, outages and plan questions. Let's see a customer journey end to end, all deployed from code in about 10 minutes." |
| 1:00-2:30 | **Flow 1: bill enquiry (Budi)** | Test chat: type `how much is my bill`, then `10012345` | "Lex recognised the intent and asked for the one thing it needed. The answer comes from the billing system (mocked here as a Lambda call), so it's deterministic. There's no generative AI on money questions." |
| 2:30-4:00 | **Flow 2: outage (Siti)** | New chat: `my wifi is down in Kemang`. Answer `Home Fiber` if asked | **Wow 1:** "It understood 'wifi' means Home Fiber and 'Kemang' means Jakarta Selatan. It matched a known incident, gave the restoration time, and opened a ticket linked to it. That's a call that never reaches an agent." |
| 4:00-5:30 | **Flow 3: generative FAQ** | Same chat: `can I pay with QRIS?` then `apakah saya bisa pakai eSIM?` | **Wow 2:** "No intent was built for either question. Bedrock answered from the policy document only, and it answered the second one in Bahasa Indonesia because the customer asked in Bahasa." |
| 5:30-6:30 | **Guardrail moment** | `can I pay with bitcoin?` | **Wow 3:** "The answer isn't in the document, so the model says it doesn't know and we escalate. It doesn't make something up. That's the behaviour your compliance team wants to see." Show Dewi's CCP ringing. |
| 6:30-8:00 | **Agent hand-off (Dewi)** | Accept the chat in the CCP. Show the transcript so far and the contact attributes (`botLastIntent`, `botTicketId`, `botAccountStatus`) | **Wow 4:** "Dewi sees the whole bot conversation and the ticket number. The customer doesn't repeat themselves, and handle time drops." Type a reply, then end the chat. |
| 8:00-9:30 | **Contact Lens** | Contact search > open the contact you just finished > Contact Lens | **Wow 5:** "Sentiment per turn, a generated post-contact summary, and sensitive data redaction on the transcript. That's QA coverage on 100% of contacts instead of a 2% sample." *(Post-chat analytics take a few minutes, so have an earlier contact ready.)* |
| 9:30-10:00 | **Close** | Show the cost table in the README | "This session cost less than a dollar. There are no seats and no idle cost. A pilot on one line of business is cheap and reversible. Proposed next step: a 2-hour discovery on your top 10 contact reasons." |

## Lines to have ready (Rina)

- "The whole environment is one CloudFormation stack. The flow is JSON in git, the bot is in the template, and the Lambda is Python."
- "Changing the FAQ is a document edit, not a model retrain."
- "Bedrock calls use an APAC-only inference profile, and there's an IAM policy for exactly one model."

## Objection handling

| Objection | Response |
|---|---|
| "Gen AI will hallucinate to our customers." | "It's only on the fallback path and grounded in one approved document. When the answer isn't there it escalates, as you just saw. In production we add Bedrock Guardrails with a contextual grounding check and denied topics, and Contact Lens shows us every AI answer for QA." |
| "Our data can't leave Indonesia." | "Connect isn't offered in Jakarta today, so the nearest Region is Singapore. Bedrock calls stay in APAC Regions through the APAC profile. We'd map which data elements are processed where, against UU PDP and OJK requirements, and redact PII in analytics. If strict in-country processing is mandatory for voice, we'd look at a hybrid with on-prem Cisco and Connect for digital channels." |
| "Does it speak Bahasa?" | "The generative layer already does, as you saw. Lex has an Indonesian locale with some feature limits, so we'd pilot ASR quality with your real recordings before committing to Bahasa voice self-service." |
| "We just renewed Cisco UCCE." | "You don't need a big-bang migration. Start with chat and AI self-service on Connect, and transfer to UCCE agents over SIP/PSTN. Move voice queues when the UCCE renewal or hardware refresh comes up." |
| "Per-minute pricing scares finance." | "Let's model it with your actual minutes. Seat licences plus hardware plus SWSS on the Cisco side is the comparison. Per-minute usually wins for seasonal or growing volume. If not, we'll show you where the crossover is." |
| "How long to production?" | "For this scope, roughly 12-14 weeks and about 78 person-days plus contingency. See the SOW template. Most of the time goes to integrations and UAT, not to the Connect build." |
| "What about our Indonesian phone numbers?" | "Connect doesn't sell Indonesian DIDs today. We'd keep your current numbers with the carrier and forward them, or use UIFN or a partner carrier. That's a discovery item we'd validate early." |

## Reset between demos

- Close finished chats in the CCP (clear After Contact Work), and set Dewi back to Available.
- Nothing else needs a reset: the mock data is stateless and ticket IDs are derived from the session.
- To show the after-hours branch, redeploy with `AGENT_HOURS=BusinessHours` and demo outside 08:00-22:00 WIB.
