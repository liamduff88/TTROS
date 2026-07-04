# LinkedIn / Content Workflow

Raw idea, transcript, client lesson, or website topic → LinkedIn post →
Instagram caption → carousel outline → CTA → optional PDF lead magnet
outline. Owned by the Marketing Agent.

## Input types
- Raw idea or one-line thought
- Call/meeting transcript
- Client lesson or result (anonymized until approved)
- Website page or existing copy
- Voice note transcript

## Output types
- LinkedIn post (final draft)
- Instagram caption
- Carousel outline (slide-by-slide)
- CTA line
- Optional PDF lead magnet outline (structure only, not the designed PDF)

## Folder convention
```
workflows/linkedin_content/
  inbox/        raw ideas, transcripts, dropped-in source material
  drafts/       in-progress posts, captions, outlines
  approved/     Liam-approved, ready to publish or hand off
  published/    what actually went out, for reuse and reference
```
One topic = one file, named `YYYY-MM-DD-short-slug.md`, carried through
the folders as it moves (moved, not copied, so there's one source of truth).

## Workflow stages
1. **Capture** — raw input dropped into `inbox/`.
2. **Draft** — Marketing Agent turns it into a LinkedIn post in `drafts/`.
3. **Expand** — same file gains an Instagram caption and carousel outline.
4. **CTA** — a single clear call to action is added.
5. **Lead magnet check** — if the topic supports it, add a one-page PDF
   outline (headings only, no design).
6. **Approve** — Liam reviews in `drafts/`, moves to `approved/` once
   happy, or sends back with notes for one redraft.
7. **Publish** — Liam posts manually; file moves to `published/` with the
   date and where it ran.

## Approval rules
- Nothing leaves `drafts/` without Liam's explicit approval.
- No automated posting. Ever. This workflow produces drafts, not sends.
- One redraft pass is the default; more needs Liam to ask directly.
- No unsupported claims or invented results in any output type.

## Connects to PDF branding workflow (later)
Once a lead magnet outline is approved in `approved/`, it becomes the
input brief for `workflows/pdf_branding` (Codex-owned). This workflow
stops at the outline; it does not touch PDF design or branding files.

## Connects to Hermes Marketing Agent
This workflow is the Marketing Agent's home turf. The orchestrator
delegates a single topic at a time; the agent works the file through
`inbox/` → `drafts/`, then hands back to Liam for approval. No content
gets created outside this folder structure without a reason.

## Connects to Revenue Agent
Once a piece is in `approved/` or `published/`, its core angle (the hook,
the lesson, the position taken) is fair game for the Revenue Agent to
reuse as an outreach angle or conversation starter. Revenue never quotes
unapproved drafts.

## First implementation step
Create the four folders above under `workflows/linkedin_content/`, drop
one real raw idea into `inbox/`, and run it through Marketing Agent once
end to end to prove the stages work before adding more topics.
