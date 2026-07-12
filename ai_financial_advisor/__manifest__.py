# -*- coding: utf-8 -*-
{
    'name': 'AI Financial Advisor & Position Report (Multi-Provider)',
    'version': '2.2.0',                    # bumped: admin-managed AI Model Catalog
    'category': 'Accounting/Reporting',
    'sequence': 10,
    'summary': 'AI-powered Financial Analysis with Claude, ChatGPT, DeepSeek, Grok & Gemini — with a fully admin-managed AI Model Catalog',
    'description': """
AI Financial Advisor & Position Report (Multi-Provider)
=========================================================
Computes a full financial position report (balance sheet, income statement,
KPIs, expense/revenue/supplier breakdowns) directly from posted Odoo
Accounting entries, then sends that data to an AI provider of your choice —
Claude, ChatGPT, Gemini, DeepSeek, or Grok — to generate an executive
summary, a 0-100 financial health score, and specific, numbered
recommendations on income, expenses, purchasing, and financial risk.

Key features:
- Admin-managed AI Model Catalog: add/archive models from the UI, no code
  or module update needed when a provider ships a new model.
- Per-report provider/model selection, so the same period can be analyzed
  by multiple providers for comparison.
- Test Connection buttons per provider in Settings.
- Printable PDF export of any analysis.

See the full walkthrough with screenshots below.
""",
    'author': 'Allam Bushra',
    'website': 'https://www.linkedin.com/in/lomixyz/',
    'license': 'LGPL-3',

    'depends': [
        'account',
        'account_reports',
        'base_setup',
        'web',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/ai_financial_model_config_views.xml',
        'data/ai_financial_model_config_data.xml',
        'views/ai_financial_report_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/ai_financial_wizard_views.xml',
        'report/ai_financial_report_action.xml',
        'report/ai_financial_report_template.xml',
        'data/repair_stale_ai_model_settings.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'ai_financial_advisor/static/src/css/ai_financial.css',
            'ai_financial_advisor/static/src/js/ai_financial_dashboard.js',
        ],
    },

    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],

    'installable': True,
    'auto_install': False,
    'application': True,
    'price': 7.0,
    'currency': 'EUR',

    # === REMOVED problematic hooks ===
    # 'post_init_hook': 'post_init_hook',
    # 'post_load': 'post_load_hook',

    'external_dependencies': {
        'python': ['requests'],
    },
}