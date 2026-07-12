# -*- coding: utf-8 -*-
"""
AI Model Catalog
─────────────────
Lets administrators add, edit, archive and reorder the exact AI model
identifiers offered everywhere "AI Model" is selected — Settings ▸ AI
Financial Advisor, the AI Financial Report form, and the report-creation
wizard — *without ever touching Python code* when a vendor ships a new
model or retires an old one.

This is the single source of truth that res_config_settings.py,
ai_financial_report.py and ai_financial_wizard.py all read from.
"""
from odoo import api, fields, models, _


class AIFinancialModelConfig(models.Model):
    _name = 'ai.financial.model.config'
    _description = 'AI Model Catalog'
    _order = 'provider, sequence, display_name'
    _rec_name = 'display_name'

    sequence = fields.Integer(default=10)

    provider = fields.Selection([
        ('claude', 'Claude (Anthropic)'),
        ('chatgpt', 'ChatGPT (OpenAI)'),
        ('deepseek', 'DeepSeek'),
        ('grok', 'Grok (X)'),
        ('gemini', 'Gemini (Google)'),
    ], string='AI Provider', required=True, index=True)

    name = fields.Char(
        string='Model ID',
        required=True,
        help='The EXACT technical model identifier sent to the provider '
             'API, e.g. "claude-sonnet-4-6" or "gpt-5.5". Copy this '
             'verbatim from the provider\'s official model/API '
             'documentation — a typo here will make every report using '
             'this model fail with an API error.',
    )
    display_name = fields.Char(
        string='Display Name',
        required=True,
        help='Friendly label shown in the AI Model dropdowns, e.g. '
             '"Claude Sonnet 4.6 (Recommended — Balanced)".',
    )

    state = fields.Selection([
        ('active', 'Active'),
        ('legacy', 'Legacy'),
        ('deprecated', 'Deprecated'),
    ], string='Status', default='active', required=True,
        help='Active: fully supported by the vendor right now.\n'
             'Legacy: still callable but superseded by newer models.\n'
             'Deprecated: the vendor has announced a retirement date — '
             'switch reports off this model soon.')

    is_default = fields.Boolean(
        string='Default for Provider',
        help='Automatically suggested when this provider is chosen and '
             'no model has been picked yet. Only one model per provider '
             'should be marked default — setting this will automatically '
             'un-mark any other default for the same provider.',
    )
    active = fields.Boolean(
        default=True,
        help='Uncheck (archive) to hide this model from every selection '
             'dropdown without losing the record — handy once a vendor '
             'retires it, while keeping history on past reports intact.',
    )
    notes = fields.Char(
        string='Notes',
        help='Optional free-text note, e.g. a retirement date, pricing '
             'tier, or context-window size.',
    )

    color = fields.Integer(string='Color', default=0)

    _sql_constraints = [
        (
            'name_provider_uniq',
            'unique(name, provider)',
            'This Model ID already exists for this AI Provider — '
            'each model only needs to be added once.',
        ),
    ]

    # ─────────────────────────────────────────────────────────────────
    # Keep "Default for Provider" unique per provider
    # ─────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.is_default:
                rec._clear_other_defaults()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_default'):
            for rec in self:
                rec._clear_other_defaults()
        return res

    def _clear_other_defaults(self):
        self.ensure_one()
        others = self.search([
            ('provider', '=', self.provider),
            ('is_default', '=', True),
            ('id', '!=', self.id),
        ])
        if others:
            others.write({'is_default': False})

    # ─────────────────────────────────────────────────────────────────
    # Display
    # ─────────────────────────────────────────────────────────────────
    def name_get(self):
        result = []
        for rec in self:
            label = rec.display_name or rec.name
            if rec.name and rec.name not in label:
                label = f'{label} ({rec.name})'
            result.append((rec.id, label))
        return result

    @api.onchange('display_name', 'name')
    def _onchange_suggest_display_name(self):
        if self.name and not self.display_name:
            self.display_name = self.name

    # ─────────────────────────────────────────────────────────────────
    # Public API consumed by res_config_settings.py / ai_financial_report.py
    # ─────────────────────────────────────────────────────────────────
    @api.model
    def get_models_for_provider(self, provider):
        """Return [(model_id, display_name), ...] for a provider — used
        to build dynamic Selection options (Settings ▸ AI Model)."""
        records = self.search([
            ('provider', '=', provider),
            ('active', '=', True),
        ])
        return [(rec.name, rec.display_name) for rec in records]

    @api.model
    def get_default_for_provider(self, provider):
        """Return the catalog record marked as default for a provider,
        or an empty recordset if none is marked / found."""
        return self.search([
            ('provider', '=', provider),
            ('is_default', '=', True),
            ('active', '=', True),
        ], limit=1)
