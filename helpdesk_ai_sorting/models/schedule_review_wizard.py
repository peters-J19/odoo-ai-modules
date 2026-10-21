from odoo import fields, models


class ScheduleReviewWizard(models.TransientModel):
    _name = "helpdesk_ai_sorting.schedule_review_wizard"
    _description = "Confirm the AI-suggested review before scheduling it"

    ticket_id = fields.Many2one("helpdesk.ticket", required=True)
    assignee_id = fields.Many2one("res.users", required=True, string="Reviewer")
    deadline = fields.Date(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.ticket_id.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=self.assignee_id.id,
            date_deadline=self.deadline,
            summary="AI-suggested review",
            note=f"Requested via AI Analysis on ticket #{self.ticket_id.id}.",
        )
        return {"type": "ir.actions.act_window_close"}
