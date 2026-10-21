{
    "name": "Helpdesk AI Sorting",
    "summary": "AI-assisted triage and escalation for helpdesk tickets",

    "description": """
AI assisted sorting design as a triage for helpdesk tickets. This
module is intended to categorize and prioritize tickets to differentiate
records that need extra AI assistance, and give said assistance, from
simpler records that don't.
""",

    "author": "Jacob Peters",
    "website": "https://github.com/peters-J19/odoo-ai-modules",
    "category": "Services/Helpdesk",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "application": False,
    "installable": True,

    "depends": [
        "helpdesk",
        "ai",
        "hr",
        "hr_skills",
        "semantic_record_search",
    ],

    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/ir_actions_server.xml",
        "views/helpdesk_ticket_views.xml",
        "views/schedule_review_wizard_views.xml",
    ],

    "demo": [
        "demo/demo.xml",
    ],
}
