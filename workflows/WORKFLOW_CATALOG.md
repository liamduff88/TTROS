# Workflow Catalog

This catalog lists reusable local business workflow packs. It is a library aid only: it helps start a clean local run folder and intake packet later.

The workflow shell does not execute workflow logic, call models, publish content, send messages, write CRM records, create client deliverables, or mutate external systems.

## Available Workflow Packs

| Workflow ID | Name | Owner Agent | Source | Intake |
| --- | --- | --- | --- | --- |
| `linkedin_content` | LinkedIn / Content Workflow | Marketing | `workflows/linkedin_content/workflow.md` | `workflows/linkedin_content/inbox` |
| `pdf_branding` | Time to Revenue PDF Branding Workflow | Marketing | `workflows/pdf_branding/README.md` | `workflows/pdf_branding/input` |
| `marketing_pdf_package` | Marketing PDF Package Workflow | Marketing | `workflows/marketing_pdf_package/workflow.md` | `workflows/marketing_pdf_package/templates/package_brief.md` |
| `revenue_linkedin_outreach` | Revenue LinkedIn Relationship Outreach Workflow | Revenue | `workflows/revenue_linkedin_outreach/workflow.md` | `workflows/revenue_linkedin_outreach/templates/prospect_brief.md` |
| `delivery_ops_documents` | Delivery / Operations Document Workflow | Delivery | `workflows/delivery_ops_documents/workflow.md` | `workflows/delivery_ops_documents/input` |
| `revenue_sales_prep` | Revenue Sales Prep Workflow | Revenue | `workflows/revenue_sales_prep/workflow.md` | `workflows/revenue_sales_prep/templates/intake_template.md` |
| `marketing_content_repurposing` | Marketing Content Repurposing Workflow | Marketing | `workflows/marketing_content_repurposing/workflow.md` | `workflows/marketing_content_repurposing/templates/intake_template.md` |
| `delivery_client_kickoff` | Delivery Client Kickoff Workflow | Delivery | `workflows/delivery_client_kickoff/workflow.md` | `workflows/delivery_client_kickoff/templates/intake_template.md` |
| `operations_founder_review` | Operations Founder Review Workflow | Operations | `workflows/operations_founder_review/workflow.md` | `workflows/operations_founder_review/templates/intake_template.md` |

## Local Shell Commands

```bash
python3 tools/aos-workflow.py list
python3 tools/aos-workflow.py show revenue_sales_prep
python3 tools/aos-workflow.py prepare revenue_sales_prep --run-id example_run --dry-run
python3 tools/aos-workflow.py prepare revenue_sales_prep --run-id example_run
```

Prepared runs are created under:

```text
results/workflow_runs/<workflow_id>/<run_id>/
```

Each prepared run contains a local packet with workflow metadata, intake path, output placeholder, receipt placeholder, human review reminder, and a reminder that no external action has been taken.
