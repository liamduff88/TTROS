# LinkedIn Outreach Pack

Work item: AOS-2026-0019
Status: draft only / unsent
Prepared for: Time to Revenue
Target segment: SMEs with manual follow-up drag, CRM disorder, missed lead risk, disconnected AI experiments, or slow speed-to-lead.

## Source Context Used

Repo pointers used:
- queue/work_items.jsonl
- queue/templates/revenue_linkedin_outreach.prompt.md
- workflows/revenue_linkedin_outreach/workflow.md
- workflows/revenue_linkedin_outreach/templates/outreach_pack.md
- agents/revenue.card.md
- context/ACCESS_MODEL.md
- context/MEMORY_ROOT.md
- memory_index/README.md

Business Brain pointers used:
- memory/company.md
- memory/positioning.md
- memory/ideal_clients.md
- memory/offers.md
- memory/sales_and_revenue.md
- memory/marketing_voice.md

No live LinkedIn, CRM, connector, browser automation, scraping, sending, posting, or external writes were used.

## Target Segment Summary

Growing service SMEs, typically owner-led or operator-led, where revenue is already leaking because enquiries, calls, follow-ups, handoffs, notes, and CRM records depend on people remembering manual steps. The best-fit prospect has real demand, an existing sales/admin workflow, and leadership urgency to make follow-up faster and cleaner without handing external actions to uncontrolled AI.

## Prospect Criteria

Prioritise prospects that show at least two of these signals:
- They rely on forms, calls, voicemail, DMs, referrals, or quote requests where response time matters.
- They mention growth, hiring, new locations, service expansion, or operational bottlenecks.
- Their team appears to use multiple disconnected tools for CRM, email, calendars, job management, support, or spreadsheets.
- Their public content hints at high enquiry volume, busy operations, missed-call risk, or admin strain.
- They are experimenting with AI tools but do not appear to have controlled workflows, approval paths, or data discipline.
- They sell considered services where a missed or slow follow-up can lose a real opportunity.

Good operational profiles:
- 5-50 owner-led SMEs with clear inbound demand but fragile follow-up.
- 25-100 growth SMEs with admin/coordinator/reception/handoff pressure.
- 100-500 mid-market service businesses where departments have started disconnected AI experiments.

Disqualifiers / pause conditions:
- Wants spam, scraping, or fully automated outreach.
- Wants unsupported ROI promises or a magic AI fix without process ownership.
- No clear workflow to improve.
- No evidence of lead-response, CRM, knowledge, admin, or follow-up friction.
- Regulated or sensitive-data use case where requirements are unclear and need deeper scoping first.

## Prospect Research Plan

For each prospect, verify manually before outreach:
1. Business model: service type, geography, buyer journey, likely enquiry paths.
2. Trigger: hiring, growth, expansion, busy season, new service line, funding, merger, or operational post.
3. Revenue leak hypothesis: slow response, missed calls, inconsistent follow-up, CRM hygiene, scattered notes, manual handoffs, or AI tool sprawl.
4. Human-relevance path: Liam/network overlap, local relevance, BNI/partner route, shared business problem, or practical comment on something they publicly posted.
5. Safe opening: a specific public observation or operational pattern, not a claim about their internal performance.
6. Disqualification check: avoid if outreach would require private data, scraping, invented intent, unsupported claims, or pressure tactics.

## LinkedIn Search / Research Instructions

Use manual LinkedIn research or an explicitly approved connector path only. Do not send, connect, scrape, enrich, or mutate CRM.

Suggested searches:
- Founder OR Owner OR Managing Director + service business + Vancouver / BC / Canada
- Operations Manager OR Revenue Operations OR Sales Manager + SME + service company
- companies hiring "admin assistant", "receptionist", "sales coordinator", "customer success", "operations coordinator"
- posts mentioning "missed calls", "follow up", "CRM", "admin", "lead response", "AI tools", "automation", "too busy", "scaling operations"
- MSPs, agencies, clinics, trades, professional services, private training providers, B2B services, home services, and local multi-location service operators

What to capture for Liam review:
- Prospect name, role, company, LinkedIn URL.
- Public trigger or relevance note.
- Hypothesised operational pain category.
- Why now.
- Draft angle selected.
- Any unsupported facts that must be verified before use.

## Outreach Angles

### 1. Slow speed-to-lead / missed enquiry angle

Use when the prospect likely receives calls, forms, referrals, quote requests, or inbound enquiries where a delayed response loses the moment.

Relationship angle:
- Lead with the common operational pattern: demand exists, but response speed depends on manual triage.
- Position TTR as helping build controlled follow-up systems, not generic AI automation.

Connection request option:
```text
Hi [Name] — I work with service businesses on faster lead response and cleaner follow-up systems. Your role at [Company] looked relevant, so I thought it would be good to connect.
```

First-touch message option:
```text
Hi [Name] — thanks for connecting.

I’m speaking with more SME operators who have enough inbound demand, but the follow-up path is still too manual: calls, forms, voicemails, CRM updates, and handoffs all depending on someone catching everything quickly.

Time to Revenue builds practical AI-enabled revenue and operations systems around that problem — faster response, cleaner notes, and human approval where it matters.

Not pitching a tool. Just curious whether speed-to-lead or follow-up consistency is on your radar this year?
```

Follow-up option:
```text
Quick follow-up, [Name] — the pattern I’m watching is not usually “we need more AI.” It’s “we are losing time between enquiry and action.”

If useful, I can send over the simple checklist I use to spot where leads slow down before they become revenue conversations.
```

CRM-ready note:
- Angle: speed-to-lead / missed enquiry.
- Hypothesis: response time and follow-up consistency may be limiting revenue conversion.
- CTA: ask whether speed-to-lead is on their radar; offer checklist only if invited.

### 2. CRM mess / scattered follow-up angle

Use when the prospect appears to have sales/admin complexity, multiple teams, coordinator roles, or a likely CRM hygiene problem.

Relationship angle:
- Avoid saying their CRM is messy. Frame it as a common scaling issue where process outgrows the original setup.

Connection request option:
```text
Hi [Name] — I help growing service businesses clean up the gap between sales follow-up, CRM notes, and daily operations. Thought it would be useful to connect.
```

First-touch message option:
```text
Hi [Name] — appreciate the connection.

A common issue I’m seeing in growing service businesses is that the CRM exists, but the real follow-up process still lives across inboxes, call notes, spreadsheets, memory, and “I’ll update that later.”

Time to Revenue helps turn that into a working revenue system: cleaner capture, clearer next steps, and practical AI support without removing human judgment.

Is CRM follow-up discipline something your team is actively improving, or not a priority right now?
```

Follow-up option:
```text
No pressure, [Name]. If it is useful, the first place I usually look is not the CRM itself — it is the handoff points before and after a sales conversation where context gets lost.

Happy to share the questions I use to diagnose that.
```

CRM-ready note:
- Angle: CRM follow-up and handoff hygiene.
- Hypothesis: CRM exists but follow-up context may be fragmented.
- CTA: ask if CRM follow-up discipline is a current priority.

### 3. Manual admin bottleneck angle

Use when the prospect is hiring admin/coordinator roles, posting about being busy, or appears dependent on manual scheduling, intake, quoting, or client onboarding steps.

Relationship angle:
- Respect current team effort; frame AI systems as reducing friction, not replacing people.

Connection request option:
```text
Hi [Name] — I work on practical AI operations for service businesses with too much manual admin around leads, follow-up, and client handoffs. Thought I’d connect.
```

First-touch message option:
```text
Hi [Name] — thanks for connecting.

One operational pattern I’m focused on is where good teams are still losing too much time to manual admin around lead capture, follow-up, booking, notes, and internal handoffs.

The goal is not to replace judgment. It is to make the repeatable parts move faster so the team can focus on the conversations that actually need them.

Is reducing manual follow-up/admin load something you are looking at, or is it not the right timing?
```

Follow-up option:
```text
Makes sense if timing is not right, [Name]. If helpful later, I can share a simple way to map which admin steps should stay manual, become hybrid, or be safely automated with approval.
```

CRM-ready note:
- Angle: manual admin drag.
- Hypothesis: repeated admin work may be slowing revenue response and operations.
- CTA: ask whether reducing manual follow-up/admin load is being considered.

### 4. Disconnected AI experiments angle

Use when the prospect is posting about AI, has team members experimenting with tools, or appears to be adopting AI without a clear operating system.

Relationship angle:
- Do not criticise. Position around control, governance, and practical workflow value.

Connection request option:
```text
Hi [Name] — I’m focused on practical AI operations: turning scattered AI experiments into controlled business workflows. Thought it would be good to connect.
```

First-touch message option:
```text
Hi [Name] — appreciate the connection.

A lot of businesses are past the “should we try AI?” stage. The harder question now is whether the experiments are actually connected to a revenue or operations workflow, with the right controls around data, approvals, and follow-up.

That is where Time to Revenue tends to work: practical AI-enabled systems, not AI theatre.

Are you currently trying to turn AI experiments into something more operational, or keeping it informal for now?
```

Follow-up option:
```text
Quick follow-up, [Name] — the useful line I see is between “people using AI tools” and “the business has a controlled workflow that reliably moves work forward.”

If useful, I can send over a short filter for deciding which AI experiments are worth operationalising.
```

CRM-ready note:
- Angle: disconnected AI experiments to controlled workflows.
- Hypothesis: AI use may be present but not operationally integrated.
- CTA: ask whether they are operationalising AI experiments.

### 5. Missed calls / voicemail leakage angle

Use when the business has phone-heavy inbound, appointment booking, field teams, clinics, trades, agencies, or after-hours enquiry risk.

Relationship angle:
- Frame as customer-experience and revenue leakage, not criticism of responsiveness.

Connection request option:
```text
Hi [Name] — I help service businesses tighten the gap between inbound calls, missed enquiries, follow-up, and booked conversations. Thought I’d connect.
```

First-touch message option:
```text
Hi [Name] — thanks for connecting.

For a lot of service businesses, the revenue leak is not demand. It is what happens when a call is missed, a voicemail waits, or a follow-up depends on someone having enough time between everything else.

Time to Revenue builds practical systems for faster capture and follow-up, with human approval where needed.

Is missed-call or voicemail follow-up something you are already solving, or not a live issue?
```

Follow-up option:
```text
No worries if it is not relevant, [Name]. I’m mainly looking for businesses where the first five minutes after an enquiry actually matter.

If that is a real issue for your team, happy to compare notes.
```

CRM-ready note:
- Angle: missed-call / voicemail leakage.
- Hypothesis: phone-based enquiry follow-up may be a revenue leakage point.
- CTA: ask if missed-call or voicemail follow-up is a live issue.

### 6. Partner / referral route angle

Use for MSPs, accountants, agencies, coaches, consultants, or local operators who may see the problem across clients.

Relationship angle:
- Start as peer/partner conversation, not direct sale.

Connection request option:
```text
Hi [Name] — I work on practical AI-enabled revenue and operations systems for growing service businesses. Looks like there may be some useful overlap in the clients we both see.
```

First-touch message option:
```text
Hi [Name] — thanks for connecting.

I’m spending more time with service businesses where the issue is not lack of opportunity, but slow follow-up, scattered data, manual handoffs, or AI experiments that are not tied to a real workflow.

Given your work with [client type/market], I wondered if you are seeing the same pattern: businesses want leverage, but do not yet have the operating structure to make AI useful safely.

Would be interested to compare notes if relevant.
```

Follow-up option:
```text
Quick follow-up, [Name] — if useful, I can share the operational signals I use to spot when a business is ready for a practical AI systems build versus when it just needs process cleanup first.
```

CRM-ready note:
- Angle: partner/referral intelligence.
- Hypothesis: potential partner sees similar operational pain in their client base.
- CTA: compare notes; no referral ask in first touch.

## Unsupported Facts / Claims To Verify Before Use

Do not use any of the following unless verified for a specific prospect:
- That they are missing leads.
- That their CRM is messy.
- That their team is slow to respond.
- That they have revenue losses from follow-up gaps.
- That they use specific CRM, AI, telephony, or workflow tools.
- That they have client results, funding, hiring needs, expansion plans, or internal AI initiatives.
- Any ROI, savings, conversion lift, case study, or guaranteed timeline claim.

Safe phrasing:
- "A common pattern I’m seeing..."
- "I’m looking for businesses where..."
- "If this is relevant..."
- "Is this on your radar?"
- "Not sure if this applies to your team..."

Avoid phrasing:
- "You are losing leads."
- "Your CRM is a mess."
- "We can guarantee..."
- "AI will replace..."
- "I noticed your team is failing to..."

## Liam Approval Needed Before

- Sending any connection request.
- Sending any LinkedIn message.
- Publishing or commenting externally.
- CRM/GHL record creation, update, tagging, note-writing, or stage movement.
- Using live LinkedIn/browser/connector automation.
- Making pricing, scope, timeline, ROI, or proof claims.
- Referring to specific client examples or private founder history beyond approved public positioning.

## Review Status

- Draft only.
- Human review required before any external action.
- Send status: not sent by workflow.
- CRM status: not changed by workflow.
- External systems touched: none.
