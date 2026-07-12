# -*- coding: utf-8 -*-
"""
AI Financial Advisor - Configuration Settings
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .ai_provider_service import AIProviderFactory

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ====================== General Settings ======================
    preferred_ai_provider = fields.Selection([
        ('claude', 'Claude (Anthropic)'),
        ('chatgpt', 'ChatGPT (OpenAI)'),
        ('deepseek', 'DeepSeek'),
        ('grok', 'Grok (X)'),
        ('gemini', 'Gemini (Google)'),
    ], string='Default AI Provider',
       config_parameter='ai_financial_advisor.default_provider',
       default='claude')

    ai_auto_analyze = fields.Boolean(
        string='Auto-run AI after Compute',
        config_parameter='ai_financial_advisor.auto_analyze',
        default=False,
    )

    ai_max_tokens = fields.Integer(
        string='Max Tokens for AI Response',
        config_parameter='ai_financial_advisor.max_tokens',
        default=4096,
    )

    # ====================== Claude ======================
    claude_api_key = fields.Char(
        string='Claude API Key',
        config_parameter='ai_financial_advisor.claude_api_key',
    )
    # The option list below is NOT hand-duplicated here: it is pulled live
    # from AIProviderFactory / ai_provider_service.py (see the
    # `_selection_*_models` methods at the bottom of this class), so the
    # dropdown and the actual API calls can never drift out of sync again.
    claude_model = fields.Selection(
        selection='_selection_claude_models',
        string='Claude Model',
        config_parameter='ai_financial_advisor.claude_model',
        default='claude-sonnet-4-6',
    )

    # ====================== ChatGPT ======================
    chatgpt_api_key = fields.Char(
        string='ChatGPT API Key',
        config_parameter='ai_financial_advisor.chatgpt_api_key',
    )
    chatgpt_model = fields.Selection(
        selection='_selection_chatgpt_models',
        string='ChatGPT Model',
        config_parameter='ai_financial_advisor.chatgpt_model',
        default='gpt-5.5',
    )

    # ====================== DeepSeek ======================
    deepseek_api_key = fields.Char(
        string='DeepSeek API Key',
        config_parameter='ai_financial_advisor.deepseek_api_key',
    )
    deepseek_model = fields.Selection(
        selection='_selection_deepseek_models',
        string='DeepSeek Model',
        config_parameter='ai_financial_advisor.deepseek_model',
        default='deepseek-v4-flash',
    )

    # ====================== Grok ======================
    grok_api_key = fields.Char(
        string='Grok API Key',
        config_parameter='ai_financial_advisor.grok_api_key',
    )
    grok_model = fields.Selection(
        selection='_selection_grok_models',
        string='Grok Model',
        config_parameter='ai_financial_advisor.grok_model',
        default='grok-4.3',
    )

    # ====================== Gemini ======================
    gemini_api_key = fields.Char(
        string='Gemini API Key',
        help='Get your API key from https://aistudio.google.com/app/apikey',
        config_parameter='ai_financial_advisor.gemini_api_key',
    )
    gemini_model = fields.Selection(
        selection='_selection_gemini_models',
        string='Gemini Model',
        config_parameter='ai_financial_advisor.gemini_model',
        default='gemini-3.1-pro-preview',
    )

    # ====================== Dynamic Selection Sources ======================
    # Each Model dropdown above is built from the AI Model Catalog
    # (Accounting ▸ AI Financial Advisor ▸ AI Models — model
    # ai.financial.model.config), which administrators manage entirely
    # from the UI. The hardcoded list in ai_provider_service.py is only
    # used as a safety net (e.g. immediately after install, before the
    # catalog has loaded, or if every catalog row for a provider was
    # archived/deleted) so a Model dropdown is never left empty.
    def _selection_models_for(self, provider):
        Catalog = self.env['ai.financial.model.config'].sudo()
        catalog_options = Catalog.get_models_for_provider(provider)
        seen = {value for value, _label in catalog_options}

        builtin = AIProviderFactory.PROVIDERS[provider]('').get_available_models()
        fallback = [(value, label) for value, label in builtin if value not in seen]

        return catalog_options + fallback

    def _selection_claude_models(self):
        return self._selection_models_for('claude')

    def _selection_chatgpt_models(self):
        return self._selection_models_for('chatgpt')

    def _selection_deepseek_models(self):
        return self._selection_models_for('deepseek')

    def _selection_grok_models(self):
        return self._selection_models_for('grok')

    def _selection_gemini_models(self):
        return self._selection_models_for('gemini')

    # ====================== Self-Healing: stale model values ======================
    # Selection fields raise a hard ValueError if the value stored in
    # ir.config_parameter is no longer one of the live options — and
    # because res.config.settings bundles every module's settings into
    # ONE record, that single bad value breaks the *entire* Settings
    # screen for every module, not just this one. This can happen any
    # time a provider's model lineup changes (a vendor retires a model,
    # or an admin archives/renames an entry in the AI Model Catalog).
    #
    # _ai_model_param() is the single place this gets checked and (if
    # needed) repaired in the database. It's called from two places so
    # the fix can never be skipped:
    #   1) default_get() below — runs on EVERY Settings screen load, a
    #      pure Python code path that takes effect the moment the addon
    #      is reloaded (a server restart), with NO dependency on anyone
    #      remembering to click Upgrade in Apps.
    #   2) _repair_stale_ai_model_settings() — also triggered by Apps ▸
    #      Upgrade (see data/repair_stale_ai_model_settings.xml), so the
    #      database gets corrected immediately on update, before anyone
    #      even opens Settings.
    def _ai_model_param(self, provider):
        """Return a guaranteed-valid stored model id for `provider`,
        transparently repairing (and persisting) it first if the
        currently-saved value is no longer a valid option."""
        ICP = self.env['ir.config_parameter'].sudo()
        param = f'ai_financial_advisor.{provider}_model'
        current = ICP.get_param(param)

        valid_values = {value for value, _label in self._selection_models_for(provider)}
        if current and current in valid_values:
            return current  # still valid — the admin's choice is untouched

        catalog_default = self.env['ai.financial.model.config'].sudo().get_default_for_provider(provider)
        new_value = catalog_default.name if catalog_default else (
            AIProviderFactory.PROVIDERS[provider]('').get_default_model()
        )

        if new_value and new_value != current:
            _logger.info(
                "AI Financial Advisor: '%s' was set to '%s', which is no "
                "longer a valid model — resetting to '%s'.",
                param, current, new_value,
            )
            ICP.set_param(param, new_value)

        return new_value

    @api.model
    def default_get(self, fields_list):
        """Defensive safety net: guarantees the Settings screen can never
        crash from a stale AI model value again, on every single load —
        independent of whether the upgrade migration has run yet."""
        res = super().default_get(fields_list)
        for provider in ('claude', 'chatgpt', 'deepseek', 'grok', 'gemini'):
            fname = f'{provider}_model'
            if fname in res:
                res[fname] = self._ai_model_param(provider)
        return res

    @api.model
    def _repair_stale_ai_model_settings(self):
        """Triggered on every module upgrade (see
        data/repair_stale_ai_model_settings.xml) so the database is
        corrected immediately, without waiting for someone to open
        Settings first."""
        for provider in ('claude', 'chatgpt', 'deepseek', 'grok', 'gemini'):
            self._ai_model_param(provider)

    # ====================== Test Connection Methods ======================
    def action_test_claude_connection(self):
        return self._test_provider_connection('claude')

    def action_test_chatgpt_connection(self):
        return self._test_provider_connection('chatgpt')

    def action_test_deepseek_connection(self):
        return self._test_provider_connection('deepseek')

    def action_test_grok_connection(self):
        return self._test_provider_connection('grok')

    def action_test_gemini_connection(self):
        return self._test_provider_connection('gemini')

    def _test_provider_connection(self, provider_name):
        """Generic test connection method"""
        ICP = self.env['ir.config_parameter'].sudo()

        api_key = ICP.get_param(f'ai_financial_advisor.{provider_name}_api_key')
        if not api_key:
            raise UserError(_('%s API key is not configured.') % provider_name.title())

        # Use whatever model is currently selected in Settings (falling
        # back to the provider default) so "Test Connection" actually
        # verifies the model the user is about to run reports with.
        model = ICP.get_param(f'ai_financial_advisor.{provider_name}_model')

        provider = AIProviderFactory.get_provider(provider_name, api_key, model)
        if not provider:
            raise UserError(_('Failed to initialize %s provider.') % provider_name.title())

        success, message = provider.validate_api_key()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('%s Connection Test') % provider_name.title(),
                'message': message,
                'type': 'success' if success else 'danger',
                'sticky': True,
            }
        }