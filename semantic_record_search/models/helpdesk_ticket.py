from odoo import models
from odoo.tools.mail import html_to_inner_content


class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _inherit = ["helpdesk.ticket", "semantic.search.mixin"]

    def _get_embeddable_text(self):
        self.ensure_one()
        return f"{self.name or ''}\n\n{html_to_inner_content(self.description)}"
