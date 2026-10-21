from odoo import fields, models


class SemanticSearchWizard(models.TransientModel):
    _name = "semantic_record_search.semantic_search_wizard"
    _description = "Search for semantically similar helpdesk tickets"

    query_text = fields.Text(string="Search Text", required=True)
    limit = fields.Integer(string="Max Results", default=10)

    def action_search(self):
        self.ensure_one()
        tickets = self.env["helpdesk.ticket"]._find_similar(
            self.query_text, limit=self.limit
        )
        # Explicit list view id - SRS's own view (no inherit_id, no
        # relationship to Helpdesk's own UI), not whatever Helpdesk's own
        # default list view happens to be. False for "form" keeps the real,
        # native helpdesk.ticket form when drilling into one specific ticket.
        list_view = self.env.ref("semantic_record_search.semantic_search_ticket_list_view")
        return {
            "type": "ir.actions.act_window",
            "name": "Similar Tickets",
            "res_model": "helpdesk.ticket",
            "views": [(list_view.id, "list"), (False, "form")],
            "view_mode": "list,form",
            "domain": [("id", "in", tickets.ids)],
            "context": {"create": False},
            "target": "current",
            "help": "<p>No similar tickets found for this search.</p>",
        }
