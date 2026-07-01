#!/usr/bin/env python3
"""
Build script for People Ops Command Center.
Runs data_engine.py and injects JSON output into dashboard.html.
"""

import json
import os
import sys


def main():
    # Import data_engine
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import data_engine
    
    # Compute metrics
    print("Computing metrics...")
    results = data_engine.main()
    
    # Read dashboard template
    print("Loading dashboard template...")
    dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
    with open(dashboard_path, 'r', encoding='utf-8') as f:
        dashboard_html = f.read()
    
    # Inject data
    print("Injecting data into dashboard...")
    data_json = json.dumps(results, indent=2)
    dashboard_html = dashboard_html.replace('const DATA = null;', f'const DATA = {data_json};')
    
    # Write to dist/index.html
    dist_dir = os.path.join(os.path.dirname(__file__), 'dist')
    os.makedirs(dist_dir, exist_ok=True)
    output_path = os.path.join(dist_dir, 'index.html')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(dashboard_html)
    
    print(f"[OK] Dashboard built successfully: {output_path}")
    print(f"[OK] Total candidates: {results['pipeline_health']['summary']['total_candidates']}")
    print(f"[OK] SLA warnings: {results['pipeline_health']['summary']['warning_count']}")
    print(f"[OK] SLA critical: {results['pipeline_health']['summary']['critical_count']}")
    print(f"[OK] Open seats: {results['headcount_gaps']['summary']['total_open_seats']}")
    print(f"[OK] Critical risks: {results['headcount_gaps']['summary']['critical_risk_count']}")
    print(f"[OK] Offer acceptance rate: {results['offer_funnel']['offer_metrics']['acceptance_rate']}%")
    print(f"[OK] Early attrition rate: {results['attrition']['summary']['overall_early_attrition_rate']}%")


if __name__ == '__main__':
    main()
