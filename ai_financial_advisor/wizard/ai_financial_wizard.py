# -*- coding: utf-8 -*-
"""
AI Financial Analysis Wizard
Multi-step wizard for creating and analyzing financial reports
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AIFinancialWizard(models.TransientModel):
    _name = 'ai.financial.wizard'
    _description = 'AI Financial Report Wizard'

    # Step 1: Report Details
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=lambda self: fields.Date.today(),
    )

    # Step 2: AI Provider Selection
    ai_provider = fields.Selection([
        ('claude', 'Claude (Anthropic) - Recommended'),
        ('chatgpt', 'ChatGPT (OpenAI) - Fastest'),
        ('deepseek', 'DeepSeek - Most Affordable'),
        ('grok', 'Grok (X) - Latest'),
        ('gemini', 'Gemini (Google) - Multimodal'),
    ],
        string='AI Provider',
        required=True,
        default='claude',
    )
    ai_model_id = fields.Many2one(
        'ai.financial.model.config',
        string='AI Model',
        domain="[('provider', '=', ai_provider), ('active', '=', True)]",
        help='Optional — leave empty to use the model configured in '
             'Settings ▸ AI Financial Advisor for this provider.',
    )

    @api.onchange('ai_provider')
    def _onchange_ai_provider(self):
        """Reset / suggest a model when the provider changes."""
        if not self.ai_provider:
            self.ai_model_id = False
            return
        catalog_default = self.env['ai.financial.model.config'].get_default_for_provider(
            self.ai_provider
        )
        self.ai_model_id = catalog_default or False

    # Step 3: Analysis Options
    auto_export = fields.Boolean(
        string='Auto-export to PDF',
        default=False,
    )
    notify_manager = fields.Boolean(
        string='Notify Accounting Manager',
        default=False,
    )

    # Status
    state = fields.Selection([
        ('details', 'Report Details'),
        ('provider', 'Provider Selection'),
        ('options', 'Analysis Options'),
        ('processing', 'Processing'),
        ('complete', 'Complete'),
    ],
        default='details',
        string='State',
    )

    # Result
    report_id = fields.Many2one(
        'ai.financial.report',
        string='Generated Report',
        readonly=True,
    )

    def action_next(self):
        """Move to next step"""
        if self.state == 'details':
            # Validate dates
            if self.date_from > self.date_to:
                raise UserError(_('Date From must be before Date To'))
            self.state = 'provider'
        elif self.state == 'provider':
            self.state = 'options'
        elif self.state == 'options':
            self.state = 'processing'
            return self.action_create_report()

        return self._reopen_form()

    def action_previous(self):
        """Move to previous step"""
        if self.state == 'provider':
            self.state = 'details'
        elif self.state == 'options':
            self.state = 'provider'

        return self._reopen_form()

    def action_create_report(self):
        """Create and analyze financial report"""
        try:
            # Create report
            report = self.env['ai.financial.report'].create({
                'company_id': self.company_id.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'ai_provider': self.ai_provider,
                'ai_model_id': self.ai_model_id.id if self.ai_model_id else False,
                'ai_model': self.ai_model_id.name if self.ai_model_id else False,
            })

            # Compute financials
            report.action_compute_financials()

            # Run AI analysis
            report.action_run_ai_analysis()

            # Auto-export if requested
            if self.auto_export:
                report.action_print_report()

            self.report_id = report.id
            self.state = 'complete'

            return self._reopen_form()

        except Exception as e:
            _logger.error(f"Wizard error: {str(e)}")
            raise UserError(_(f"Report creation failed: {str(e)}"))

    def action_open_report(self):
        """Open the generated report"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.financial.report',
            'res_id': self.report_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reopen_form(self):
        """Reopen the wizard form"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }