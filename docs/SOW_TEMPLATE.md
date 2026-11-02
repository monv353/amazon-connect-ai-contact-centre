# Sample scope of work: AI-assisted contact centre on Amazon Connect

> Template for a professional-services proposal based on this repo's design. The customer, volumes and rates are illustrative. Replace everything in `<angle brackets>` and re-check prices on the day you quote.

## 1. Background

`<Customer>` (an Indonesian telco or bank) runs a `<Cisco UCCX 12.5 / UCCE / other>` contact centre with about **50 agents** handling voice and web chat in Bahasa Indonesia and English. The goals are to:

- contain routine bill and outage enquiries with self-service,
- answer policy and FAQ questions with grounded generative AI, and
- give agents the full bot context on hand-off and move QA from sampling to 100% analytics.

## 2. Scope

### In scope

| # | Workstream | Deliverables |
|---|---|---|
| 1 | **Discovery and design** | Current-state review (call drivers, IVR tree, routing, integrations, reporting). Contact reason analysis from 3 months of data. HLD and LLD, data residency and security design, test strategy |
| 2 | **Foundation** | AWS accounts and landing zone alignment (prod plus non-prod). Connect instance(s) in ap-southeast-1 through IaC (CloudFormation) and a CI/CD pipeline. SAML SSO with `<Entra ID / Okta>`. S3/KMS storage, CloudTrail, CloudWatch alarms |
| 3 | **Telephony** | Number strategy (carrier forwarding / UIFN / porting where supported; Indonesian DID availability to be confirmed with AWS). Up to 4 numbers. Coexistence transfers to the legacy platform during the transition |
| 4 | **Routing** | Up to 6 queues, 4 routing profiles, hours of operation and holidays, quick connects, agent/supervisor security profiles |
| 5 | **Self-service** | Lex V2 bot with up to **8 intents** in en_US, plus id_ID subject to pilot results. Up to 2 inbound flows (voice and chat) and 2 modules. Bedrock FAQ answering with a **Knowledge Base** (up to 200 documents) and **Guardrails** |
| 6 | **Integrations** | Up to **3 back-end APIs** (billing balance, outage status, ticket creation) through Lambda. CRM screen-pop for `<Salesforce / in-house CRM>` |
| 7 | **Analytics and QA** | Contact Lens real-time and post-contact analytics with redaction policy. Up to 10 categories/rules, 1 evaluation form, supervisor dashboards |
| 8 | **Testing** | SIT, UAT support (2 cycles), a 100-concurrent-contact load test, security review findings fixed |
| 9 | **Training and cutover** | Admin, supervisor and agent train-the-trainer (3 sessions). Runbooks. Phased cutover by queue. **2 weeks of hypercare** |

### Out of scope (can be quoted separately)

Outbound campaigns, WFM forecasting and scheduling, voice biometrics, migration of historical recordings or reports, CRM customisation beyond the screen-pop, 24x7 managed service after hypercare, and network or SD-WAN changes for agent sites.

## 3. Effort estimate (person-days by phase)

| Phase | SA | Connect engineer | Developer | QA | PM | **Total** |
|---|---:|---:|---:|---:|---:|---:|
| 1. Discovery and design | 5 | 2 | 1 | 0 | 1 | **9** |
| 2. Foundation (accounts, IaC, SSO, security) | 2 | 4 | 2 | 0 | 0.5 | **8.5** |
| 3. Telephony and coexistence | 1 | 3 | 0 | 0.5 | 0.5 | **5** |
| 4. Routing configuration | 0.5 | 3 | 0 | 0.5 | 0 | **4** |
| 5. Self-service (Lex, flows, Bedrock KB and Guardrails) | 2 | 4 | 6 | 1 | 0.5 | **13.5** |
| 6. Integrations (3 APIs and CRM screen-pop) | 1 | 1 | 7 | 1 | 0.5 | **10.5** |
| 7. Contact Lens, rules, evaluation, dashboards | 1 | 3 | 0 | 0.5 | 0 | **4.5** |
| 8. Testing (SIT, UAT, load, security) | 0.5 | 2 | 2 | 5 | 0.5 | **10** |
| 9. Training, cutover, 2-week hypercare | 1 | 4 | 1 | 0 | 1 | **7** |
| Project management and governance (weekly status, RAID, steering) | 0 | 0 | 0 | 0 | 6 | **6** |
| **Total** | **14** | **26** | **19** | **8.5** | **10.5** | **78** |

- **Contingency:** add 15% (about 12 person-days) for fixed price. Time-and-materials quotes show it separately.
- **Duration:** about 12-14 weeks elapsed. Phases 5-7 run in parallel after the LLD sign-off.
- **Price:** `78 x <blended day rate>`, or price each role from the rate card. Example: with an illustrative blended rate of USD 650 a day, 78 days comes to USD 50,700, or about USD 58,300 with contingency.

### What makes the estimate go up or down

| Up | Down |
|---|---|
| Bahasa voice self-service (ASR tuning, prompt recording) | Chat-only first phase |
| More than 3 integrations, or no ready API (needs middleware) | Customer provides the APIs and test data on time |
| Regulated-industry security assessment (OJK, PCI DSS for card payments in IVR) | Reuse of an existing AWS landing zone and SSO |
| Big-bang cutover and more than 100 agents | Phased cutover by queue |

## 4. Assumptions

1. The customer provides API specs, test environments and test data for the 3 integrations by week 4.
2. One AWS Region (ap-southeast-1). Disaster recovery through Connect Global Resiliency is not in scope; it is not offered in Singapore at the time of writing.
3. The customer owns carrier contracts and number porting or forwarding. Lead times (often 4-8 weeks) sit on the customer's critical path.
4. Knowledge Base content (FAQs, policies) is supplied approved and in digital form. Content writing is out of scope.
5. Each UAT cycle lasts 5 business days, with a named customer test lead.
6. The partner works remotely from Jakarta and Singapore. Up to 4 on-site days are included for workshops and cutover.
7. AWS service charges are paid directly by the customer and are not part of the professional-services fee.

## 5. Monthly AWS run-cost estimate (illustrative)

**Volume assumptions:** 30,000 voice contacts a month at 5 minutes each (150,000 minutes), and 20,000 chats at about 20 messages each (400,000 messages). The bot sends 30% of contacts to the Bedrock FAQ path, with about 1,100 input and 80 output tokens per call.

Prices are from the AWS Price List API for ap-southeast-1 (publication 2026-09-11) and the AWS pricing pages linked below. They are USD, before tax and before any private pricing.

### Option A: "Connect Customer" bundled pricing (the default for new instances)

| Line item | Rate | Quantity | Monthly USD |
|---|---|---|---:|
| Voice (includes Lex, Contact Lens, agent assist, evaluations, forecasting) | USD 0.038 per minute | 150,000 min | 5,700 |
| Chat (includes Lex and Contact Lens chat analytics) | USD 0.010 per message | 400,000 msg | 4,000 |
| Telephony: inbound DID minutes (Singapore DID shown; Indonesian ingress depends on carrier design) | USD 0.004 per minute | 150,000 min | 600 |
| Phone numbers (4 Singapore DIDs) | USD 0.0395 per day | 4 x 30 days | 5 |
| Bedrock Nova Lite (APAC profile) | USD 0.081 per 1M input, USD 0.324 per 1M output | about 15,000 calls | 2 |
| Lambda, S3, CloudWatch, KMS | | | about 50 |
| **Total** | | | **about 10,357** |

### Option B: per-feature ("basic") pricing, for comparison

| Line item | Rate | Quantity | Monthly USD |
|---|---|---|---:|
| Voice | USD 0.018 per minute | 150,000 min | 2,700 |
| Contact Lens voice analytics | USD 0.015 per minute | 150,000 min | 2,250 |
| Lex speech requests (about 6 per call) | USD 0.004 per request | 180,000 | 720 |
| Chat | USD 0.004 per message | 400,000 | 1,600 |
| Contact Lens chat analytics | USD 0.0015 per message | 400,000 | 600 |
| Lex text requests (about 5 per chat) | USD 0.00075 per request | 100,000 | 75 |
| Telephony, numbers, Bedrock, other | as above | | 657 |
| **Total** | | | **about 8,602** |

**How to read this:** on raw minutes and messages, option B is about 17% cheaper for this volume. Option A also bundles agent assist, generative AI summaries, evaluations, screen recording, and forecasting and scheduling, which would otherwise be extra licences or third-party WFM/QM tools. Choose by the features the customer will actually use. Confirm with AWS which pricing plan a new instance can select, because AWS has changed this in 2026. Cost per contact is about USD 0.21 (A) or USD 0.17 (B) before agent labour, which is usually 80-90% of total cost per contact.

**Sources (checked 2026-11-02):**
- Amazon Connect pricing: https://aws.amazon.com/connect/pricing/ and appendix https://aws.amazon.com/products/connect/customer/pricing/appendix/
- Price List API, Connect ap-southeast-1: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonConnect/current/ap-southeast-1/index.json
- Contact Lens ap-southeast-1: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/ContactLensAmazonConnect/current/ap-southeast-1/index.json
- Telephony ap-southeast-1: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/ContactCenterTelecomm/current/ap-southeast-1/index.json
- Amazon Lex pricing: https://aws.amazon.com/lex/pricing/ (API: .../offers/v1.0/aws/AmazonLex/current/ap-southeast-1/index.json)
- Amazon Bedrock pricing: https://aws.amazon.com/bedrock/pricing/ (API: .../offers/v1.0/aws/AmazonBedrock/current/ap-southeast-1/index.json)
- Connect telecoms coverage: https://d1v2gagwb6hfe1.cloudfront.net/Amazon_Connect_Telecoms_Coverage.pdf

## 6. Acceptance criteria (examples)

- Self-service containment of at least `<25>`% for bill and outage intents after 4 weeks in production (measured in Contact Lens or Connect metrics).
- Every escalated contact shows bot intent and context attributes in the agent workspace.
- Bedrock answers pass a 50-question golden set with no ungrounded answers. An "I don't know" answer counts as a pass.
- Contact Lens redaction verified on 20 sample contacts containing PII.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Indonesian number availability or carrier lead time | Validate in discovery. Fall back to carrier forwarding |
| Bahasa ASR accuracy for voice self-service | Pilot with 200 real recordings before committing to the scope |
| Data residency objections (UU PDP, OJK) | Early DPIA, APAC-only Bedrock profile, redaction, KMS keys owned by the customer |
| Integration APIs not ready | Mock APIs in sprint 1, with a contractual dependency date |
| Agent adoption | Super-user programme and a phased cutover |
