/** @odoo-module **/
/**
 * AI Financial Advisor — Dashboard JS
 * Odoo 17 OWL / Legacy compatible
 * Renders Chart.js charts for expense & revenue breakdowns
 */

import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { Component, onMounted, useRef } from '@odoo/owl';

// ── Chart Widget ─────────────────────────────────────────────────────────────

class AIFinancialChartWidget extends Component {
    static template = 'ai_financial_advisor.ChartWidget';
    static props = {
        reportId: { type: Number },
        chartType: { type: String },   // 'expense' | 'revenue' | 'supplier'
        title: { type: String },
    };

    setup() {
        this.rpc = useService('rpc');
        this.canvasRef = useRef('canvas');
        this.chartInstance = null;

        onMounted(async () => {
            await this._loadAndRenderChart();
        });
    }

    async _loadAndRenderChart() {
        try {
            const data = await this.rpc(
                `/ai_financial_advisor/report_data/${this.props.reportId}`, {}
            );
            if (data.error) return;

            const chartData = data[`${this.props.chartType}_chart`];
            if (!chartData || !chartData.labels.length) return;

            this._renderChart(chartData, data.currency);
        } catch (e) {
            console.warn('AI Financial Chart: Failed to load data', e);
        }
    }

    _renderChart(chartData, currency) {
        const ctx = this.canvasRef.el.getContext('2d');
        const colors = [
            '#3498db', '#27ae60', '#e74c3c', '#f39c12', '#8e44ad',
            '#1abc9c', '#e67e22', '#2ecc71', '#e91e63', '#ff5722',
        ];

        this.chartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartData.labels,
                datasets: [{
                    data: chartData.values,
                    backgroundColor: colors.slice(0, chartData.labels.length),
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { font: { size: 11 }, boxWidth: 14 },
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const val = ctx.parsed;
                                return ` ${ctx.label}: ${currency}${val.toLocaleString('en-US', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2,
                                })}`;
                            },
                        },
                    },
                },
            },
        });
    }
}

// ── Utility: Animate Health Score Counter ────────────────────────────────────

function animateHealthScore(el, targetScore) {
    if (!el) return;
    let current = 0;
    const step = Math.ceil(targetScore / 60);
    const timer = setInterval(() => {
        current = Math.min(current + step, targetScore);
        el.textContent = current;
        if (current >= targetScore) clearInterval(timer);
    }, 16);
}

// ── On-page initialization (for non-OWL legacy view enhancement) ─────────────

function initAIFinancialPage() {
    // Animate health score if present on page
    const scoreEl = document.querySelector('[data-ai-health-score]');
    if (scoreEl) {
        const score = parseInt(scoreEl.dataset.aiHealthScore, 10);
        animateHealthScore(scoreEl, score);
    }

    // Highlight negative net income in red
    document.querySelectorAll('[data-net-income]').forEach(el => {
        const val = parseFloat(el.dataset.netIncome);
        if (val < 0) {
            el.style.color = '#e74c3c';
            el.style.fontWeight = 'bold';
        } else {
            el.style.color = '#27ae60';
        }
    });
}

// Run on DOM ready
document.addEventListener('DOMContentLoaded', initAIFinancialPage);

export { AIFinancialChartWidget, animateHealthScore };
