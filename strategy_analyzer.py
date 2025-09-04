import pandas as pd
import numpy as np
from typing import Dict, List, Any
from datetime import datetime, timedelta
import yaml
import os

class StrategyAnalyzer:
    def __init__(self, config_path='enhanced_config.yaml'):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.results = {}
        self.strategy_rankings = {}
        self.index_performance = {}
        
    def analyze_strategy_performance(self, backtest_results: Dict) -> Dict:
        """Analyze individual strategy performance"""
        analysis = {}
        
        for strategy_name, performance in backtest_results.get('strategy_performance', {}).items():
            total_trades = performance.get('total_trades', 0)
            total_pnl = performance.get('total_pnl', 0)
            win_rate = performance.get('win_rate', 0)
            avg_pnl_per_trade = performance.get('avg_pnl_per_trade', 0)
            
            # Calculate additional metrics
            analysis[strategy_name] = {
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'win_rate': win_rate * 100,
                'avg_pnl_per_trade': avg_pnl_per_trade,
                'profit_consistency': self.calculate_consistency_score(performance),
                'risk_adjusted_return': self.calculate_risk_adjusted_return(performance),
                'strategy_grade': self.grade_strategy(performance)
            }
        
        return analysis
    
    def calculate_consistency_score(self, performance: Dict) -> float:
        """Calculate strategy consistency score (0-100)"""
        win_rate = performance.get('win_rate', 0)
        total_trades = performance.get('total_trades', 0)
        
        if total_trades < 10:
            return 0
        
        # Higher win rate and more trades = higher consistency
        consistency = (win_rate * 0.7) + (min(total_trades / 100, 1) * 0.3)
        return consistency * 100
    
    def calculate_risk_adjusted_return(self, performance: Dict) -> float:
        """Calculate risk-adjusted return metric"""
        total_pnl = performance.get('total_pnl', 0)
        total_trades = performance.get('total_trades', 0)
        
        if total_trades == 0:
            return 0
        
        # Simple risk adjustment based on number of trades and consistency
        avg_return = total_pnl / total_trades if total_trades > 0 else 0
        consistency_factor = self.calculate_consistency_score(performance) / 100
        
        return avg_return * consistency_factor
    
    def grade_strategy(self, performance: Dict) -> str:
        """Grade strategy from A+ to F"""
        win_rate = performance.get('win_rate', 0) * 100
        total_trades = performance.get('total_trades', 0)
        avg_pnl = performance.get('avg_pnl_per_trade', 0)
        
        score = 0
        
        # Win rate scoring (40% weight)
        if win_rate >= 70:
            score += 40
        elif win_rate >= 60:
            score += 35
        elif win_rate >= 50:
            score += 25
        elif win_rate >= 40:
            score += 15
        
        # Trade frequency scoring (30% weight)
        if total_trades >= 50:
            score += 30
        elif total_trades >= 25:
            score += 25
        elif total_trades >= 10:
            score += 20
        elif total_trades >= 5:
            score += 10
        
        # Profitability scoring (30% weight)
        if avg_pnl > 0.02:
            score += 30
        elif avg_pnl > 0.01:
            score += 25
        elif avg_pnl > 0.005:
            score += 20
        elif avg_pnl > 0:
            score += 15
        
        # Grade assignment
        if score >= 85:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 75:
            return 'A-'
        elif score >= 70:
            return 'B+'
        elif score >= 65:
            return 'B'
        elif score >= 60:
            return 'B-'
        elif score >= 55:
            return 'C+'
        elif score >= 50:
            return 'C'
        elif score >= 45:
            return 'C-'
        elif score >= 40:
            return 'D'
        else:
            return 'F'
    
    def rank_strategies(self, strategy_analysis: Dict) -> List[Dict]:
        """Rank strategies by overall performance"""
        rankings = []
        
        for strategy_name, metrics in strategy_analysis.items():
            score = (
                metrics['win_rate'] * 0.3 +
                metrics['profit_consistency'] * 0.3 +
                abs(metrics['risk_adjusted_return']) * 1000 * 0.4  # Scale for comparison
            )
            
            rankings.append({
                'strategy': strategy_name,
                'score': score,
                'grade': metrics['strategy_grade'],
                'win_rate': metrics['win_rate'],
                'total_trades': metrics['total_trades'],
                'total_pnl': metrics['total_pnl']
            })
        
        # Sort by score descending
        rankings.sort(key=lambda x: x['score'], reverse=True)
        
        return rankings
    
    def analyze_index_suitability(self, backtest_results: Dict) -> Dict:
        """Analyze which strategies work best for each index"""
        index_analysis = {}
        
        # Get index-specific configuration
        index_config = self.config.get('index_specific', {})
        
        for index_name, config in index_config.items():
            preferred_strategies = config.get('preferred_strategies', [])
            volatility_multiplier = config.get('volatility_multiplier', 1.0)
            
            index_analysis[index_name] = {
                'preferred_strategies': preferred_strategies,
                'volatility_multiplier': volatility_multiplier,
                'recommended_allocation': self.calculate_index_allocation(
                    index_name, backtest_results
                ),
                'risk_profile': 'High' if volatility_multiplier > 1.1 else 'Low' if volatility_multiplier < 0.9 else 'Medium'
            }
        
        return index_analysis
    
    def calculate_index_allocation(self, index_name: str, backtest_results: Dict) -> Dict:
        """Calculate recommended strategy allocation for an index"""
        # This is a simplified allocation model
        # In practice, you'd use more sophisticated optimization
        
        strategy_performance = backtest_results.get('strategy_performance', {})
        total_strategies = len(strategy_performance)
        
        if total_strategies == 0:
            return {}
        
        # Equal weight as starting point, then adjust based on performance
        base_allocation = 100 / total_strategies
        allocations = {}
        
        for strategy_name, performance in strategy_performance.items():
            win_rate = performance.get('win_rate', 0)
            total_pnl = performance.get('total_pnl', 0)
            
            # Adjust allocation based on performance
            performance_multiplier = (win_rate * 0.7) + (min(total_pnl / 10000, 1) * 0.3)
            allocations[strategy_name] = max(5, base_allocation * performance_multiplier)  # Minimum 5%
        
        # Normalize to 100%
        total_allocation = sum(allocations.values())
        if total_allocation > 0:
            allocations = {k: (v / total_allocation * 100) for k, v in allocations.items()}
        
        return allocations
    
    def generate_analysis_report(self, backtest_results: Dict) -> str:
        """Generate comprehensive analysis report"""
        
        strategy_analysis = self.analyze_strategy_performance(backtest_results)
        strategy_rankings = self.rank_strategies(strategy_analysis)
        index_analysis = self.analyze_index_suitability(backtest_results)
        
        report = []
        report.append("# STRATEGY ANALYSIS REPORT")
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Overall Performance Summary
        report.append("## OVERALL PERFORMANCE SUMMARY")
        total_trades = backtest_results.get('total_trades', 0)
        total_pnl = backtest_results.get('total_pnl', 0)
        win_rate = backtest_results.get('win_rate', 0)
        sharpe_ratio = backtest_results.get('sharpe_ratio', 0)
        max_drawdown = backtest_results.get('max_drawdown_pct', 0)
        
        report.append(f"- Total Trades: {total_trades}")
        report.append(f"- Total P&L: ₹{total_pnl:,.2f}")
        report.append(f"- Win Rate: {win_rate*100:.1f}%")
        report.append(f"- Sharpe Ratio: {sharpe_ratio:.2f}")
        report.append(f"- Max Drawdown: {max_drawdown:.1f}%")
        report.append("")
        
        # Strategy Rankings
        report.append("## STRATEGY RANKINGS")
        report.append("| Rank | Strategy | Grade | Score | Win Rate | Trades | P&L |")
        report.append("|------|----------|-------|-------|----------|--------|-----|")
        
        for i, ranking in enumerate(strategy_rankings, 1):
            report.append(
                f"| {i} | {ranking['strategy']} | {ranking['grade']} | "
                f"{ranking['score']:.1f} | {ranking['win_rate']:.1f}% | "
                f"{ranking['total_trades']} | ₹{ranking['total_pnl']:,.0f} |"
            )
        
        report.append("")
        
        # Index Recommendations
        report.append("## INDEX-SPECIFIC RECOMMENDATIONS")
        
        for index_name, analysis in index_analysis.items():
            report.append(f"### {index_name}")
            report.append(f"- Risk Profile: {analysis['risk_profile']}")
            report.append(f"- Volatility Multiplier: {analysis['volatility_multiplier']}")
            report.append("- Preferred Strategies:")
            
            for strategy in analysis['preferred_strategies']:
                report.append(f"  - {strategy}")
            
            report.append("")
        
        # Detailed Strategy Analysis
        report.append("## DETAILED STRATEGY ANALYSIS")
        
        for strategy_name, metrics in strategy_analysis.items():
            report.append(f"### {strategy_name.upper()}")
            report.append(f"- Grade: {metrics['strategy_grade']}")
            report.append(f"- Total Trades: {metrics['total_trades']}")
            report.append(f"- Win Rate: {metrics['win_rate']:.1f}%")
            report.append(f"- Average P&L per Trade: ₹{metrics['avg_pnl_per_trade']:,.2f}")
            report.append(f"- Consistency Score: {metrics['profit_consistency']:.1f}/100")
            report.append(f"- Risk-Adjusted Return: {metrics['risk_adjusted_return']:.4f}")
            report.append("")
        
        return "\n".join(report)
    
    def save_analysis_report(self, backtest_results: Dict, filename: str = None):
        """Save analysis report to file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"strategy_analysis_report_{timestamp}.md"
        
        report_content = self.generate_analysis_report(backtest_results)
        
        with open(filename, 'w') as file:
            file.write(report_content)
        
        print(f"✅ Analysis report saved to: {filename}")
        return filename
    
    def compare_strategies(self, strategy1: str, strategy2: str, backtest_results: Dict) -> Dict:
        """Compare two strategies head-to-head"""
        strategy_performance = backtest_results.get('strategy_performance', {})
        
        if strategy1 not in strategy_performance or strategy2 not in strategy_performance:
            return {"error": "One or both strategies not found in results"}
        
        perf1 = strategy_performance[strategy1]
        perf2 = strategy_performance[strategy2]
        
        comparison = {
            'strategy_1': {
                'name': strategy1,
                'trades': perf1.get('total_trades', 0),
                'pnl': perf1.get('total_pnl', 0),
                'win_rate': perf1.get('win_rate', 0) * 100
            },
            'strategy_2': {
                'name': strategy2,
                'trades': perf2.get('total_trades', 0),
                'pnl': perf2.get('total_pnl', 0),
                'win_rate': perf2.get('win_rate', 0) * 100
            },
            'winner': self.determine_winner(perf1, perf2)
        }
        
        return comparison
    
    def determine_winner(self, perf1: Dict, perf2: Dict) -> str:
        """Determine which strategy performs better overall"""
        score1 = (
            perf1.get('win_rate', 0) * 0.4 +
            (perf1.get('total_pnl', 0) / 10000) * 0.4 +
            (perf1.get('total_trades', 0) / 100) * 0.2
        )
        
        score2 = (
            perf2.get('win_rate', 0) * 0.4 +
            (perf2.get('total_pnl', 0) / 10000) * 0.4 +
            (perf2.get('total_trades', 0) / 100) * 0.2
        )
        
        if score1 > score2:
            return 'strategy_1'
        elif score2 > score1:
            return 'strategy_2'
        else:
            return 'tie'
