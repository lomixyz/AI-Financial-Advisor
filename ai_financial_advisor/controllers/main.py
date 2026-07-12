# -*- coding: utf-8 -*-
"""
Main Controller for AI Financial Advisor
Handles web routes and requests
"""

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class AIFinancialAdvisorController(http.Controller):
    """
    Controller for AI Financial Advisor web interface
    """

    @http.route('/ai_financial_advisor/dashboard', auth='user', type='http', website=True)
    def dashboard(self):
        """Main dashboard view"""
        try:
            # Get current user reports
            reports = request.env['ai.financial.report'].search(
                [('create_uid', '=', request.uid)],
                order='create_date desc',
                limit=10
            )

            return request.render('ai_financial_advisor.dashboard_template', {
                'reports': reports,
            })
        except Exception as e:
            _logger.error(f"Dashboard error: {str(e)}")
            return request.render('ai_financial_advisor.error_template', {
                'error': str(e),
            })

    @http.route('/ai_financial_advisor/api/providers', auth='user', type='json')
    def get_available_providers(self):
        """API endpoint to get available providers"""
        try:
            from ..models.ai_provider_service import AIProviderFactory

            providers = []
            for provider_name in AIProviderFactory.get_available_providers():
                info = AIProviderFactory.get_provider_info(provider_name)
                providers.append({
                    'name': provider_name,
                    'default_model': info['default_model'],
                    'models': info['available_models'],
                })

            return {
                'success': True,
                'providers': providers,
            }
        except Exception as e:
            _logger.error(f"Provider API error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/ai_financial_advisor/api/report/<int:report_id>/analyze',
                auth='user', type='json', methods=['POST'])
    def analyze_report(self, report_id):
        """API endpoint to analyze a report"""
        try:
            report = request.env['ai.financial.report'].browse(report_id)

            if not report.exists():
                return {
                    'success': False,
                    'error': 'Report not found',
                }

            # Run analysis
            report.action_run_ai_analysis()

            return {
                'success': True,
                'score': report.ai_overall_score,
                'label': report.ai_score_label,
            }
        except Exception as e:
            _logger.error(f"Analysis error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }