First-week acceptance checklist — safe speed-to-lead workflow
Fixture: Beacon Field Services, fictional internal test client only

Objective:
Create a safe, human-reviewed first-response workflow for web leads before any automation is trusted. No external systems, connector writes, real customer data, or outcome claims.

1. Intake definition

Acceptance checks:
- Every test lead includes: name, company, phone/email, service need, location, urgency, preferred contact method, and submitted timestamp.
- Leads missing required fields are flagged as “incomplete,” not silently processed.
- The workflow records lead received time and first-response due time.
- Test data is clearly marked fictional.

Human-review point:
- Coordinator reviews each captured lead before any response is drafted or assigned.

Failure handling:
- If required fields are missing, route to “needs clarification.”
- If urgency is unclear, default to normal priority and flag for coordinator review.
- If duplicate test leads appear, mark as possible duplicate instead of merging automatically.

Handoff step:
- Document the final intake fields and required/optional status for each.

2. Lead priority rules

Acceptance checks:
- Leads are classified into simple priority levels:
  - Urgent: active facility issue, safety concern, service interruption, or same-day need.
  - Standard: quote, inspection, recurring maintenance, or non-urgent request.
  - Incomplete: missing enough detail to classify.
- Classification uses only submitted lead content.
- No assumptions are made about revenue value, customer quality, or likelihood to close.

Human-review point:
- Coordinator approves or corrects priority before assignment.

Failure handling:
- Ambiguous leads go to “needs review.”
- Conflicting urgency signals are escalated to coordinator.

Handoff step:
- Provide a one-page priority-rule table with examples using fictional leads only.

3. Estimator assignment

Acceptance checks:
- Each reviewed lead is assigned to one estimator or marked “unassigned — needs coordinator action.”
- Assignment reason is recorded, such as geography, service type, availability, or manual coordinator choice.
- No automatic assignment is trusted without review during week one.

Human-review point:
- Coordinator confirms the estimator before the first response is sent.

Failure handling:
- If no estimator is available, route to coordinator fallback.
- If assignment confidence is low, leave unassigned rather than guessing.
- If two estimators appear suitable, coordinator chooses manually.

Handoff step:
- Create an assignment log template: lead ID, priority, estimator, reason, reviewer, timestamp.

4. First-response draft

Acceptance checks:
- Draft response includes:
  - Acknowledgement of the request.
  - Service need restated from the lead.
  - Next step.
  - Expected human follow-up.
  - Contact path for urgent correction.
- Draft does not promise availability, pricing, response speed, or service outcome unless manually added by a human.
- Draft is clearly labeled “review required.”

Human-review point:
- Human approves every outbound message during week one.

Failure handling:
- If lead content is too thin, draft asks for missing details.
- If the request appears urgent, draft is escalated before sending.
- If the request is outside known service scope, draft is held for coordinator review.

Handoff step:
- Provide three approved draft templates:
  - Standard quote request.
  - Urgent maintenance request.
  - Incomplete lead / clarification request.

5. Follow-up tracking

Acceptance checks:
- Every test lead has a visible status:
  - New
  - Reviewed
  - Assigned
  - Response approved
  - Response sent manually
  - Follow-up needed
  - Closed / no action
- Follow-up date is set manually after response approval.
- No automatic follow-up is sent in week one.

Human-review point:
- Coordinator reviews end-of-day status list and confirms no test lead is stuck in “new” or “reviewed.”

Failure handling:
- If status is unchanged after the agreed review window, flag as overdue.
- If estimator does not respond, coordinator reassigns or follows up manually.
- If a lead is closed, closure reason is recorded.

Handoff step:
- Create a daily review checklist for coordinator: new leads, overdue leads, unassigned leads, follow-ups due.

6. Safety and data boundaries

Acceptance checks:
- Only fictional fixture data is used.
- No real customer names, emails, phone numbers, inboxes, CRMs, calendars, or live workspaces are connected.
- No connector writes are performed.
- No external messages are sent.
- No secrets, API keys, or credentials are requested or exposed.

Human-review point:
- Delivery owner confirms the week-one workflow remains offline/sandboxed.

Failure handling:
- If real customer data appears, stop the run and remove it from the test set.
- If any step requires a live connector, replace it with a manual mock step.
- If a credential is encountered, do not copy or display it; stop and escalate.

Handoff step:
- Include a “safe test only” note at the top of all week-one workflow docs.

7. Week-one completion contract

The first-week workflow is acceptable only if:
- A fictional lead can move from intake to reviewed status.
- Priority can be assigned or flagged for review.
- Estimator assignment can be made or safely deferred.
- A first-response draft can be generated for human approval.
- No outbound message is sent automatically.
- Failure paths are documented for incomplete, ambiguous, duplicate, urgent, and unassigned leads.
- Coordinator handoff materials exist: intake field list, priority table, assignment log, draft templates, and daily review checklist.
- All outputs avoid real customer data and unsupported performance claims.

Token usage: unavailable
