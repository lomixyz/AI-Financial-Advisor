# -*- coding: utf-8 -*-
"""
Enhanced AI Financial Report Model
Now supports Claude, ChatGPT, DeepSeek, and Grok providers
"""
import html
import json
import logging
import re
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .ai_provider_service import AIProviderFactory

_logger = logging.getLogger(__name__)


class AIFinancialReport(models.Model):
    _name = 'ai.financial.report'
    _description = 'AI Financial Position Report'
    _order = 'create_date desc'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Report Name',
        compute='_compute_name',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string='Date From',
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=lambda self: date.today(),
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('ai_analyzed', 'AI Analyzed'),
    ], default='draft', string='Status', tracking=True)

    def unlink(self):
        locked = self.filtered(lambda r: r.state in ('computed', 'ai_analyzed'))
        if locked:
            raise UserError(_(
                'You cannot delete a report that has already been computed or '
                'analyzed (%s). Use "Reset to Draft" first if you need to delete it.'
            ) % ', '.join(locked.mapped('name')))
        return super().unlink()

    # ── AI Provider Selection ─────────────────────────────────────────────────
    ai_provider = fields.Selection([
        ('claude', 'Claude (Anthropic)'),
        ('chatgpt', 'ChatGPT (OpenAI)'),
        ('deepseek', 'DeepSeek'),
        ('grok', 'Grok (X)'),
        ('gemini', 'Gemini (Google)'),
    ],
        string='AI Provider',
        default='claude',
        tracking=True,
    )
    ai_model_id = fields.Many2one(
        'ai.financial.model.config',
        string='AI Model',
        domain="[('provider', '=', ai_provider), ('active', '=', True)]",
        help='Pick the exact model to use for this report. Leave empty '
             'to use whatever is configured in Settings ▸ AI Financial '
             'Advisor for this provider.',
    )
    ai_model = fields.Char(
        string='AI Model (Technical ID)',
        help='Technical model identifier actually sent to the provider '
             'API. Filled in automatically from the selection above.',
    )

    # ── Financial Data (Assets) ───────────────────────────────────────────────
    total_assets = fields.Monetary(string='Total Assets', currency_field='currency_id')
    current_assets = fields.Monetary(string='Current Assets', currency_field='currency_id')
    non_current_assets = fields.Monetary(string='Non-Current Assets', currency_field='currency_id')
    cash_and_equivalents = fields.Monetary(string='Cash & Equivalents', currency_field='currency_id')
    accounts_receivable = fields.Monetary(string='Accounts Receivable', currency_field='currency_id')
    inventory = fields.Monetary(string='Inventory', currency_field='currency_id')
    fixed_assets = fields.Monetary(string='Fixed Assets', currency_field='currency_id')

    # ── Financial Data (Liabilities) ──────────────────────────────────────────
    total_liabilities = fields.Monetary(string='Total Liabilities', currency_field='currency_id')
    current_liabilities = fields.Monetary(string='Current Liabilities', currency_field='currency_id')
    non_current_liabilities = fields.Monetary(string='Non-Current Liabilities', currency_field='currency_id')
    accounts_payable = fields.Monetary(string='Accounts Payable', currency_field='currency_id')
    short_term_debt = fields.Monetary(string='Short-Term Debt', currency_field='currency_id')
    long_term_debt = fields.Monetary(string='Long-Term Debt', currency_field='currency_id')

    # ── Financial Data (Equity) ───────────────────────────────────────────────
    total_equity = fields.Monetary(string='Total Equity', currency_field='currency_id')

    # ── P&L Data ──────────────────────────────────────────────────────────────
    total_revenue = fields.Monetary(string='Total Revenue', currency_field='currency_id')
    total_expenses = fields.Monetary(string='Total Expenses', currency_field='currency_id')
    gross_profit = fields.Monetary(string='Gross Profit', currency_field='currency_id')
    net_income = fields.Monetary(string='Net Income / (Loss)', currency_field='currency_id')
    operating_expenses = fields.Monetary(string='Operating Expenses', currency_field='currency_id')
    cost_of_goods_sold = fields.Monetary(string='Cost of Goods Sold (COGS)', currency_field='currency_id')

    # ── KPIs ──────────────────────────────────────────────────────────────────
    current_ratio = fields.Float(string='Current Ratio', digits=(16, 2))
    debt_to_equity = fields.Float(string='Debt-to-Equity Ratio', digits=(16, 2))
    gross_margin_pct = fields.Float(string='Gross Margin %', digits=(16, 2))
    net_margin_pct = fields.Float(string='Net Margin %', digits=(16, 2))
    return_on_assets = fields.Float(string='Return on Assets %', digits=(16, 2))

    # ── Expense Breakdown (JSON) ──────────────────────────────────────────────
    # NOTE: these store raw JSON text, not HTML markup. They must be Text,
    # not Html — Odoo auto-sanitizes Html fields (wraps content in <p>
    # tags, HTML-escapes quotes/ampersands, etc.), which silently corrupts
    # JSON written into them and makes json.loads() fail later with
    # "Expecting value: line 1 column 1" on the mangled <p>{...}</p> text.
    expense_breakdown_json = fields.Text(string='Expense Breakdown (JSON)')
    revenue_breakdown_json = fields.Text(string='Revenue Breakdown (JSON)')
    top_suppliers_json = fields.Text(string='Top Suppliers by Spend (JSON)')

    # ── AI Recommendations ────────────────────────────────────────────────────
    ai_summary = fields.Html(string='AI Executive Summary', sanitize=False)
    ai_income_recommendations = fields.Html(string='AI Income Increase Recommendations', sanitize=False)
    ai_expense_recommendations = fields.Html(string='AI Expense Reduction Recommendations', sanitize=False)
    ai_purchasing_recommendations = fields.Html(string='AI Purchasing Optimization', sanitize=False)
    ai_risk_alerts = fields.Html(string='AI Risk Alerts', sanitize=False)
    ai_overall_score = fields.Integer(string='Financial Health Score (0-100)')
    ai_score_label = fields.Char(string='Health Label')
    ai_generated_at = fields.Datetime(string='AI Analysis Generated At')

    # ── Line Items ────────────────────────────────────────────────────────────
    expense_line_ids = fields.One2many(
        'ai.financial.report.line',
        'report_id',
        string='Expense Lines',
        domain=[('line_type', '=', 'expense')],
    )
    revenue_line_ids = fields.One2many(
        'ai.financial.report.line',
        'report_id',
        string='Revenue Lines',
        domain=[('line_type', '=', 'revenue')],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Compute
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('date_from', 'date_to', 'company_id')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Financial Position — %s to %s (%s)') % (
                rec.date_from or '', rec.date_to or '', rec.company_id.name or ''
            )

    @api.onchange('ai_provider')
    def _onchange_ai_provider(self):
        """Suggest a model when the provider changes: prefer whatever is
        marked "Default for Provider" in the AI Model Catalog, falling
        back to the provider's built-in default if the catalog has
        nothing for it yet (e.g. right after install)."""
        if not self.ai_provider:
            self.ai_model_id = False
            self.ai_model = False
            return

        catalog_default = self.env['ai.financial.model.config'].get_default_for_provider(
            self.ai_provider
        )
        if catalog_default:
            self.ai_model_id = catalog_default
            self.ai_model = catalog_default.name
        else:
            self.ai_model_id = False
            provider_info = AIProviderFactory.get_provider_info(self.ai_provider)
            self.ai_model = provider_info['default_model'] if provider_info else False

    @api.onchange('ai_model_id')
    def _onchange_ai_model_id(self):
        """Keep the technical Char field in sync with the catalog pick."""
        if self.ai_model_id:
            self.ai_model = self.ai_model_id.name

    # ─────────────────────────────────────────────────────────────────────────
    # Core: Compute Financial Data from Odoo Accounting
    # ─────────────────────────────────────────────────────────────────────────

    def action_compute_financials(self):
        """Pull all financial data from account.move.line entries."""
        self.ensure_one()
        company = self.company_id
        date_from = self.date_from
        date_to = self.date_to

        # Helper: sum balance for account types within date range.
        # NOTE: the inner parameters are deliberately named differently from
        # the outer `date_from`/`date_to` variables above. Naming them the
        # same would *shadow* the outer variables inside this closure, so a
        # call like get_balance([...], cumulative=True) — which relies on
        # the outer date_to — would silently see None instead, turning the
        # SQL filter into `date <= NULL` (matches nothing). That was the
        # root cause of the Balance Sheet always computing to 0.00 while
        # the Income Statement (which passes its dates explicitly) worked.
        def get_balance(account_types, from_date=None, to_date=None, cumulative=False):
            domain = [
                ('company_id', '=', company.id),
                ('account_id.account_type', 'in', account_types),
                ('move_id.state', '=', 'posted'),
            ]
            if cumulative:
                # Balance sheet accounts (assets/liabilities/equity) are
                # point-in-time balances: sum every posted entry up to the
                # period end date, regardless of the period start date.
                domain += [('date', '<=', to_date or date_to)]
            else:
                if from_date:
                    domain += [('date', '>=', from_date)]
                if to_date:
                    domain += [('date', '<=', to_date)]

            lines = self.env['account.move.line'].search(domain)
            return sum(lines.mapped('balance'))

        # ── Assets ────────────────────────────────────────────────────────────
        cash = get_balance(['asset_cash'], cumulative=True)
        receivable = get_balance(['asset_receivable'], cumulative=True)
        inventory_val = get_balance(['asset_current'], cumulative=True)
        fixed = get_balance(['asset_non_current', 'asset_fixed'], cumulative=True)

        current_assets = cash + receivable + inventory_val
        non_current_assets = fixed
        total_assets = current_assets + non_current_assets

        # ── Liabilities ───────────────────────────────────────────────────────
        payable = abs(get_balance(['liability_payable'], cumulative=True))
        current_liab = abs(get_balance(['liability_current'], cumulative=True)) + payable
        long_term = abs(get_balance(['liability_non_current'], cumulative=True))
        total_liabilities = current_liab + long_term

        # ── Equity ────────────────────────────────────────────────────────────
        equity = abs(get_balance(['equity', 'equity_unaffected'], cumulative=True))

        # ── P&L ───────────────────────────────────────────────────────────────
        revenue = abs(get_balance(['income', 'income_other'], from_date=date_from, to_date=date_to))
        cogs = abs(get_balance(['expense_direct_cost'], from_date=date_from, to_date=date_to))
        opex = abs(get_balance(['expense'], from_date=date_from, to_date=date_to))
        total_expenses = cogs + opex
        gross_profit = revenue - cogs
        net_income = revenue - total_expenses

        # ── Write values ──────────────────────────────────────────────────────
        self.write({
            'total_assets': total_assets,
            'current_assets': current_assets,
            'non_current_assets': non_current_assets,
            'cash_and_equivalents': cash,
            'accounts_receivable': receivable,
            'inventory': inventory_val,
            'fixed_assets': fixed,
            'total_liabilities': total_liabilities,
            'current_liabilities': current_liab,
            'non_current_liabilities': long_term,
            'accounts_payable': payable,
            'total_equity': equity,
            'total_revenue': revenue,
            'total_expenses': total_expenses,
            'gross_profit': gross_profit,
            'net_income': net_income,
            'cost_of_goods_sold': cogs,
            'operating_expenses': opex,
        })

        # ── Compute KPIs ──────────────────────────────────────────────────────
        self._compute_kpis()

        # ── Compute breakdowns ────────────────────────────────────────────────
        self._compute_expense_breakdown()
        self._compute_revenue_breakdown()
        self._compute_top_suppliers()

        self.state = 'computed'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Financial Data Computed'),
                'message': _('All financial metrics have been calculated successfully.'),
                'sticky': False,
                'type': 'success',
            }
        }

    def _compute_kpis(self):
        """Compute key performance indicators."""
        current_ratio = (
            self.current_assets / self.current_liabilities
            if self.current_liabilities > 0 else 0
        )

        debt_to_equity = (
            self.total_liabilities / self.total_equity
            if self.total_equity > 0 else 0
        )

        gross_margin = (
            (self.gross_profit / self.total_revenue * 100)
            if self.total_revenue > 0 else 0
        )

        net_margin = (
            (self.net_income / self.total_revenue * 100)
            if self.total_revenue > 0 else 0
        )

        roa = (
            (self.net_income / self.total_assets * 100)
            if self.total_assets > 0 else 0
        )

        self.write({
            'current_ratio': current_ratio,
            'debt_to_equity': debt_to_equity,
            'gross_margin_pct': gross_margin,
            'net_margin_pct': net_margin,
            'return_on_assets': roa,
        })

    def _compute_expense_breakdown(self):
        """Compute expense breakdown by account."""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', '=', 'expense'),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]

        lines = self.env['account.move.line'].search(domain)
        breakdown = {}
        for line in lines:
            account_name = line.account_id.name
            breakdown[account_name] = breakdown.get(account_name, 0) + abs(line.balance)

        sorted_breakdown = dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:10])
        self.expense_breakdown_json = json.dumps(sorted_breakdown)

    def _compute_revenue_breakdown(self):
        """Compute revenue breakdown by account."""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', 'in', ['income', 'income_other']),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]

        lines = self.env['account.move.line'].search(domain)
        breakdown = {}
        for line in lines:
            account_name = line.account_id.name
            breakdown[account_name] = breakdown.get(account_name, 0) + abs(line.balance)

        sorted_breakdown = dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:10])
        self.revenue_breakdown_json = json.dumps(sorted_breakdown)

    def _compute_top_suppliers(self):
        """Compute top suppliers by spend."""
        domain = [
            ('company_id', '=', self.company_id.id),
            ('account_id.account_type', '=', 'liability_payable'),
        ]
        lines = self.env['account.move.line'].search(domain)
        suppliers = {}
        for line in lines:
            partner = line.partner_id.name if line.partner_id else 'Unknown'
            suppliers[partner] = suppliers.get(partner, 0) + abs(line.balance)

        sorted_suppliers = dict(sorted(suppliers.items(), key=lambda x: x[1], reverse=True)[:10])
        self.top_suppliers_json = json.dumps(sorted_suppliers)

    # ─────────────────────────────────────────────────────────────────────────
    # AI Analysis with Multi-Provider Support
    # ─────────────────────────────────────────────────────────────────────────

    def action_run_ai_analysis(self):
        """Send financial data to selected AI provider and get recommendations."""
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(
                _('Please compute financial data first before running AI analysis.')
            )

        # Get API configuration
        provider_name = self.ai_provider or 'claude'
        ICP = self.env['ir.config_parameter'].sudo()

        api_key = ICP.get_param(f'ai_financial_advisor.{provider_name}_api_key')
        if not api_key:
            raise UserError(_(
                'API key for %s is not configured.\n'
                'Go to Settings → AI Financial Advisor → %s API Key.'
            ) % (provider_name.title(), provider_name.title()))

        # Resolve which model to actually call:
        #  1) an explicit per-report pick (ai_model_id) always wins — that's
        #     the whole point of exposing the AI Model selector on the report,
        #  2) otherwise the technical ai_model Char (covers records created
        #     programmatically without going through the form's onchange),
        #  3) otherwise whatever is configured in Settings for this provider.
        settings_model = ICP.get_param(f'ai_financial_advisor.{provider_name}_model')
        explicit_model = self.ai_model_id.name if self.ai_model_id else False
        resolved_model = explicit_model or self.ai_model or settings_model or None
        source = 'report selection' if explicit_model else (
            'report (technical field)' if self.ai_model else (
                'settings' if settings_model else 'provider default'
            )
        )

        # Keep both UI fields in sync with whatever was actually used, so
        # the form never shows a stale model after analysis.
        sync_vals = {}
        if resolved_model and resolved_model != self.ai_model:
            sync_vals['ai_model'] = resolved_model
        if resolved_model and not self.ai_model_id:
            catalog_match = self.env['ai.financial.model.config'].search([
                ('provider', '=', provider_name),
                ('name', '=', resolved_model),
            ], limit=1)
            if catalog_match:
                sync_vals['ai_model_id'] = catalog_match.id
        if sync_vals:
            self.write(sync_vals)

        _logger.info(
            'AI Analysis: provider=%s  model=%s  source=%s',
            provider_name, resolved_model, source,
        )

        # Build prompt
        prompt = self._build_ai_prompt()

        # Get AI provider and call API
        provider = AIProviderFactory.get_provider(
            provider_name,
            api_key,
            resolved_model,
        )

        if not provider:
            raise UserError(_('Invalid AI provider selected.'))

        # Respect the "Max Tokens for AI Response" setting instead of a
        # hardcoded value, falling back to 4096 if it was never set.
        max_tokens = int(ICP.get_param('ai_financial_advisor.max_tokens', default='4096') or 4096)

        # Call the API
        success, response_text, error = provider.call_api(prompt, max_tokens=max_tokens)

        if not success:
            raise UserError(_('AI Analysis Failed:\n%s') % error)

        # Parse structured response
        self._parse_ai_response(response_text)
        self.ai_generated_at = fields.Datetime.now()
        self.state = 'ai_analyzed'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Analysis Complete'),
                'message': _('AI recommendations from %s have been generated successfully.') % provider_name.title(),
                'sticky': False,
                'type': 'success',
            }
        }

    def _safe_json_loads(self, value):
        """Parse a stored breakdown JSON field, tolerating data saved
        before expense_breakdown_json/revenue_breakdown_json/
        top_suppliers_json were Html fields (Odoo's HTML sanitizer wraps
        content in tags and HTML-escapes quotes/ampersands, which breaks
        plain json.loads()). Falls back to an empty dict instead of
        crashing the whole AI Analysis run — re-running "Compute" on the
        report regenerates clean data going forward.
        """
        if not value:
            return {}
        text = value.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        # Likely old HTML-sanitized data: strip any wrapper tags and
        # un-escape HTML entities, then try again.
        cleaned = html.unescape(re.sub(r'<[^>]+>', '', text)).strip()
        if not cleaned:
            return {}
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError, ValueError):
            _logger.warning(
                'AI Financial Report %s: could not parse stored breakdown '
                'JSON even after cleanup — using empty data. Raw value '
                'started with: %r', self.id, value[:80],
            )
            return {}

    def _build_ai_prompt(self):
        """Build the detailed financial prompt for the AI."""
        expense_data = self._safe_json_loads(self.expense_breakdown_json)
        revenue_data = self._safe_json_loads(self.revenue_breakdown_json)
        supplier_data = self._safe_json_loads(self.top_suppliers_json)

        currency = self.currency_id.symbol or '$'

        expense_lines = '\n'.join(
            [f'  - {k}: {currency}{v:,.2f}' for k, v in list(expense_data.items())[:10]]
        ) or '  No data'

        revenue_lines = '\n'.join(
            [f'  - {k}: {currency}{v:,.2f}' for k, v in list(revenue_data.items())[:10]]
        ) or '  No data'

        supplier_lines = '\n'.join(
            [f'  - {k}: {currency}{v:,.2f}' for k, v in list(supplier_data.items())[:10]]
        ) or '  No data'

        prompt = f"""You are a senior financial advisor and CFO consultant analyzing a company's financial position. 
Provide actionable, specific, and realistic recommendations based on the data below.

## Company Financial Report
**Period:** {self.date_from} to {self.date_to}
**Company:** {self.company_id.name}
**Currency:** {self.currency_id.name}

---

### BALANCE SHEET SUMMARY
**ASSETS**
- Total Assets: {currency}{self.total_assets:,.2f}
- Current Assets: {currency}{self.current_assets:,.2f}
  - Cash & Equivalents: {currency}{self.cash_and_equivalents:,.2f}
  - Accounts Receivable: {currency}{self.accounts_receivable:,.2f}
  - Inventory: {currency}{self.inventory:,.2f}
- Non-Current Assets: {currency}{self.non_current_assets:,.2f}
  - Fixed Assets: {currency}{self.fixed_assets:,.2f}

**LIABILITIES**
- Total Liabilities: {currency}{self.total_liabilities:,.2f}
- Current Liabilities: {currency}{self.current_liabilities:,.2f}
  - Accounts Payable: {currency}{self.accounts_payable:,.2f}
- Non-Current Liabilities: {currency}{self.non_current_liabilities:,.2f}

**EQUITY**
- Total Equity: {currency}{self.total_equity:,.2f}

---

### INCOME STATEMENT SUMMARY
- Total Revenue: {currency}{self.total_revenue:,.2f}
- Cost of Goods Sold: {currency}{self.cost_of_goods_sold:,.2f}
- Gross Profit: {currency}{self.gross_profit:,.2f}
- Operating Expenses: {currency}{self.operating_expenses:,.2f}
- Total Expenses: {currency}{self.total_expenses:,.2f}
- Net Income: {currency}{self.net_income:,.2f}

---

### KEY PERFORMANCE INDICATORS
- Current Ratio: {self.current_ratio:.2f} (ideal: >1.5)
- Debt-to-Equity Ratio: {self.debt_to_equity:.2f} (ideal: <2.0)
- Gross Margin: {self.gross_margin_pct:.1f}%
- Net Margin: {self.net_margin_pct:.1f}%
- Return on Assets: {self.return_on_assets:.1f}%

---

### TOP EXPENSE ACCOUNTS
{expense_lines}

### TOP REVENUE ACCOUNTS
{revenue_lines}

### TOP SUPPLIERS BY SPEND
{supplier_lines}

---

## YOUR TASK

Analyze this financial data carefully and provide your response in EXACTLY this format (use these exact section headers):

[EXECUTIVE_SUMMARY]
Write a 3-4 sentence executive summary of the company's financial health, highlighting the most critical points.

[FINANCIAL_HEALTH_SCORE]
Give a score from 0 to 100 representing overall financial health. Just the number, nothing else.

[INCOME_RECOMMENDATIONS]
Provide 5 specific, actionable recommendations to increase income/revenue. Number each one. Be specific with percentages, timeframes, and methods relevant to the data shown.

[EXPENSE_RECOMMENDATIONS]
Provide 5 specific, actionable recommendations to reduce expenses and costs. Number each one. Reference the actual expense categories shown in the data. Include estimated savings where possible.

[PURCHASING_RECOMMENDATIONS]
Provide 4 specific recommendations about purchasing optimization, supplier negotiations, and avoiding unnecessary procurement. Reference actual suppliers if visible. Include tactics like bulk purchasing, supplier consolidation, or payment terms renegotiation.

[RISK_ALERTS]
Identify 3 key financial risks or red flags that the accountant should address immediately, based on the KPIs and data provided.

Be direct, professional, and specific. Avoid generic advice — tailor everything to the actual numbers shown."""

        return prompt

    def _parse_ai_response(self, text):
        """Extract structured sections from AI response."""

        def extract_section(tag, content):
            start = content.find(f'[{tag}]')
            if start == -1:
                return ''
            start += len(f'[{tag}]')
            # Find next section tag
            import re
            next_tag = re.search(r'\[[A-Z_]+\]', content[start:])
            if next_tag:
                return content[start:start + next_tag.start()].strip()
            return content[start:].strip()

        summary = extract_section('EXECUTIVE_SUMMARY', text)
        score_text = extract_section('FINANCIAL_HEALTH_SCORE', text)
        income_recs = extract_section('INCOME_RECOMMENDATIONS', text)
        expense_recs = extract_section('EXPENSE_RECOMMENDATIONS', text)
        purchasing_recs = extract_section('PURCHASING_RECOMMENDATIONS', text)
        risk_alerts = extract_section('RISK_ALERTS', text)

        # Parse score
        try:
            import re
            score_match = re.search(r'\d+', score_text)
            score = int(score_match.group()) if score_match else 50
            score = max(0, min(100, score))
        except Exception:
            score = 50

        # Determine label
        if score >= 80:
            label = 'Excellent'
        elif score >= 65:
            label = 'Good'
        elif score >= 50:
            label = 'Fair'
        elif score >= 35:
            label = 'Needs Attention'
        else:
            label = 'Critical'

        def text_to_html(text):
            """Convert plain AI text to clean readable HTML.
            Handles markdown-style bold (**text**), bullet lines (- or *),
            numbered lists, and blank-line paragraphs.
            """
            import re as _re
            if not text:
                return ''

            lines = text.split('\n')
            html_lines = []
            in_ul = False
            in_ol = False

            def close_lists():
                nonlocal in_ul, in_ol
                result = ''
                if in_ul:
                    result += '</ul>'
                    in_ul = False
                if in_ol:
                    result += '</ol>'
                    in_ol = False
                return result

            def format_inline(line):
                # Bold: **text** or __text__
                line = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                line = _re.sub(r'__(.+?)__', r'<strong>\1</strong>', line)
                # Italic: *text* or _text_
                line = _re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', line)
                return line

            for line in lines:
                stripped = line.strip()

                if not stripped:
                    html_lines.append(close_lists())
                    continue

                # Numbered list: "1. text"
                num_match = _re.match(r'^(\d+)\.\s+(.*)', stripped)
                if num_match:
                    if in_ul:
                        html_lines.append('</ul>')
                        in_ul = False
                    if not in_ol:
                        html_lines.append('<ol>')
                        in_ol = True
                    html_lines.append(f'<li>{format_inline(num_match.group(2))}</li>')
                    continue

                # Bullet list: "- text" or "* text" or "• text"
                bullet_match = _re.match(r'^[-*•]\s+(.*)', stripped)
                if bullet_match:
                    if in_ol:
                        html_lines.append('</ol>')
                        in_ol = False
                    if not in_ul:
                        html_lines.append('<ul>')
                        in_ul = True
                    html_lines.append(f'<li>{format_inline(bullet_match.group(1))}</li>')
                    continue

                # Heading-like lines (ALL CAPS or ending with :)
                if stripped.isupper() and len(stripped) > 3:
                    html_lines.append(close_lists())
                    html_lines.append(f'<h4 style="margin-top:12px;margin-bottom:6px;">{format_inline(stripped.title())}</h4>')
                    continue

                # Normal paragraph line
                html_lines.append(close_lists())
                html_lines.append(f'<p style="margin:4px 0;line-height:1.6;">{format_inline(stripped)}</p>')

            html_lines.append(close_lists())
            return '\n'.join(filter(None, html_lines))

        self.write({
            'ai_summary': text_to_html(summary),
            'ai_overall_score': score,
            'ai_score_label': label,
            'ai_income_recommendations': text_to_html(income_recs),
            'ai_expense_recommendations': text_to_html(expense_recs),
            'ai_purchasing_recommendations': text_to_html(purchasing_recs),
            'ai_risk_alerts': text_to_html(risk_alerts),
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_print_report(self):
        return self.env.ref(
            'ai_financial_advisor.action_ai_financial_report_pdf'
        ).report_action(self)

    def action_reset_to_draft(self):
        self.state = 'draft'


class AIFinancialReportLine(models.Model):
    _name = 'ai.financial.report.line'
    _description = 'AI Financial Report Line Item'
    _order = 'amount desc'

    report_id = fields.Many2one('ai.financial.report', string='Report', ondelete='cascade')
    name = fields.Char(string='Account / Category', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one(related='report_id.currency_id')
    percentage = fields.Float(string='% of Total', digits=(16, 2))
    line_type = fields.Selection([
        ('expense', 'Expense'),
        ('revenue', 'Revenue'),
    ], string='Type', required=True)
    note = fields.Char(string='AI Note')