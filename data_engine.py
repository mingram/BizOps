#!/usr/bin/env python3
"""
Pure Python data processing module for People Ops Command Center.
No external dependencies - uses only Python standard library.
"""

import csv
import json
import re
import os
from datetime import datetime
from collections import defaultdict


def load_csv(filepath):
    """Load CSV file and return list of dictionaries."""
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def parse_offer_letter(filepath):
    """Parse offer letter text file and extract key fields using regex."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract candidate ID
    candidate_id_match = re.search(r'Candidate ID:\s*(C\d+)', content)
    candidate_id = candidate_id_match.group(1) if candidate_id_match else None
    
    # Extract base salary
    base_salary_match = re.search(r'Base Salary:\s*\$([\d,]+)', content)
    base_salary = int(base_salary_match.group(1).replace(',', '')) if base_salary_match else None
    
    # Extract equity grant
    equity_match = re.search(r'Equity Grant:\s*\$([\d,]+)', content)
    equity_grant = int(equity_match.group(1).replace(',', '')) if equity_match else 0
    
    # Extract signing bonus (scoped to the SIGNING BONUS section so that a
    # "No signing bonus is included" note is not confused with dollar amounts
    # from later sections such as the benefits stipends).
    signing_bonus = 0
    signing_section_match = re.search(
        r'SIGNING BONUS\s*\n[\u2500\-=_]+\s*\n(.*?)(?:\n[\u2500\-=_]{3,}|\Z)',
        content, re.DOTALL | re.IGNORECASE)
    if signing_section_match:
        amount_match = re.search(r'\$([\d,]+)', signing_section_match.group(1))
        if amount_match:
            signing_bonus = int(amount_match.group(1).replace(',', ''))
    
    # Extract start date
    start_date_match = re.search(r'Start Date:\s*(.+?)(?:\n|$)', content)
    start_date = start_date_match.group(1).strip() if start_date_match else None
    
    return {
        'candidate_id': candidate_id,
        'base_salary': base_salary,
        'equity_grant': equity_grant,
        'signing_bonus': signing_bonus,
        'start_date': start_date
    }


def compute_pipeline_health(pipeline_data, stage_targets=None):
    """Compute pipeline health with time-in-stage target breach detection."""
    if stage_targets is None:
        stage_targets = {
            'Applied': 3,
            'Phone Screen': 7,
            'Technical/Assessment': 10,
            'Hiring Manager Interview': 10,
            'Final Round': 14,
            'Offer Extended': 5,
            'Offer Accepted': 5
        }
    
    results = []
    warning_count = 0
    critical_count = 0
    
    for row in pipeline_data:
        candidate_id = row['candidate_id']
        current_stage = row['current_stage']
        days_in_stage = int(row['days_in_current_stage']) if row['days_in_current_stage'] else 0
        
        target = stage_targets.get(current_stage, 7)
        status = 'OK'
        
        if days_in_stage > target * 2:
            status = 'Critical'
            critical_count += 1
        elif days_in_stage > target:
            status = 'Warning'
            warning_count += 1
        
        results.append({
            'candidate_id': candidate_id,
            'candidate_name': row['candidate_name'],
            'current_stage': current_stage,
            'days_in_stage': days_in_stage,
            'target': target,
            'status': status
        })
    
    return {
        'candidates': results,
        'summary': {
            'total_candidates': len(results),
            'warning_count': warning_count,
            'critical_count': critical_count
        }
    }


def compute_headcount_gaps(headcount_plan, pipeline_data):
    """Compute headcount gaps by joining headcount plan to active pipeline."""
    # Count active pipeline by department and level
    pipeline_counts = defaultdict(int)
    for row in pipeline_data:
        if row['disposition'] == 'Active':
            key = (row['department'], row['level'])
            pipeline_counts[key] += 1
    
    results = []
    critical_risks = []
    
    for row in headcount_plan:
        department = row['department']
        level = row['level']
        open_seats = int(row['open_seats'])
        priority = row['priority']
        
        key = (department, level)
        active_pipeline = pipeline_counts.get(key, 0)
        
        # Risk calculation
        risk = 'Low'
        if open_seats > 0 and active_pipeline == 0 and priority == 'High':
            risk = 'Critical'
            critical_risks.append({
                'department': department,
                'level': level,
                'open_seats': open_seats,
                'priority': priority
            })
        elif open_seats > 0 and active_pipeline == 0:
            risk = 'Medium'
        elif open_seats > 0 and active_pipeline < open_seats / 2:
            risk = 'Medium'
        
        results.append({
            'department': department,
            'level': level,
            'approved_headcount': int(row['approved_headcount']),
            'filled_seats': int(row['filled_seats']),
            'open_seats': open_seats,
            'active_pipeline': active_pipeline,
            'priority': priority,
            'risk': risk
        })
    
    return {
        'gaps': results,
        'critical_risks': critical_risks,
        'summary': {
            'total_open_seats': sum(r['open_seats'] for r in results),
            'total_active_pipeline': sum(r['active_pipeline'] for r in results),
            'critical_risk_count': len(critical_risks)
        }
    }


def compute_offer_funnel(pipeline_data):
    """Compute offer funnel metrics."""
    stage_counts = defaultdict(int)
    offer_extended = 0
    offer_accepted = 0
    offer_declined = 0
    offer_negotiating = 0
    
    for row in pipeline_data:
        stage = row['current_stage']
        stage_counts[stage] += 1
        
        if stage == 'Offer Extended':
            offer_extended += 1
        elif stage == 'Offer Accepted':
            offer_accepted += 1
        elif row['disposition'] == 'Declined':
            offer_declined += 1
        elif row['disposition'] == 'Negotiating':
            offer_negotiating += 1
    
    acceptance_rate = (offer_accepted / (offer_extended + offer_accepted)) * 100 if (offer_extended + offer_accepted) > 0 else 0
    
    return {
        'stage_counts': dict(stage_counts),
        'offer_metrics': {
            'offer_extended': offer_extended,
            'offer_accepted': offer_accepted,
            'offer_declined': offer_declined,
            'offer_negotiating': offer_negotiating,
            'acceptance_rate': round(acceptance_rate, 1)
        }
    }


def compute_offer_reconciliation(offer_log, offer_letters_dir):
    """Reconcile offer letters with offer log CSV."""
    # Load offer letters
    offer_letters = {}
    for filename in os.listdir(offer_letters_dir):
        if filename.endswith('.txt'):
            filepath = os.path.join(offer_letters_dir, filename)
            parsed = parse_offer_letter(filepath)
            if parsed['candidate_id']:
                offer_letters[parsed['candidate_id']] = parsed
    
    # Create offer log lookup
    offer_log_lookup = {}
    for row in offer_log:
        candidate_id = row['candidate_id']
        offer_log_lookup[candidate_id] = {
            'base_salary': float(row['base_salary_usd']) if row['base_salary_usd'] else None,
            'equity_grant': float(row['equity_grant_usd']) if row['equity_grant_usd'] else 0,
            'signing_bonus': float(row['signing_bonus_usd']) if row['signing_bonus_usd'] else 0,
            'start_date': row['start_date']
        }
    
    # Reconcile
    reconciliations = []
    mismatches = []
    
    for candidate_id, letter_data in offer_letters.items():
        log_data = offer_log_lookup.get(candidate_id)
        
        if not log_data:
            mismatches.append({
                'candidate_id': candidate_id,
                'issue': 'Not found in offer_log.csv'
            })
            continue
        
        # Compare fields
        issues = []
        if letter_data['base_salary'] != log_data['base_salary']:
            issues.append(f"Base salary mismatch: letter=${letter_data['base_salary']}, log=${log_data['base_salary']}")
        if letter_data['equity_grant'] != log_data['equity_grant']:
            issues.append(f"Equity mismatch: letter=${letter_data['equity_grant']}, log=${log_data['equity_grant']}")
        if letter_data['signing_bonus'] != log_data['signing_bonus']:
            issues.append(f"Signing bonus mismatch: letter=${letter_data['signing_bonus']}, log=${log_data['signing_bonus']}")
        
        status = 'Matched' if not issues else 'Mismatch'
        
        reconciliations.append({
            'candidate_id': candidate_id,
            'letter_base_salary': letter_data['base_salary'],
            'log_base_salary': log_data['base_salary'],
            'letter_equity': letter_data['equity_grant'],
            'log_equity': log_data['equity_grant'],
            'letter_signing_bonus': letter_data['signing_bonus'],
            'log_signing_bonus': log_data['signing_bonus'],
            'status': status,
            'issues': issues
        })
        
        if issues:
            mismatches.append({
                'candidate_id': candidate_id,
                'issue': '; '.join(issues)
            })
    
    return {
        'reconciliations': reconciliations,
        'mismatches': mismatches,
        'summary': {
            'total_letters': len(offer_letters),
            'matched': len([r for r in reconciliations if r['status'] == 'Matched']),
            'mismatched': len(mismatches)
        }
    }


def compute_attrition(people_events):
    """Compute early attrition analysis from people events."""
    terminations = []
    early_attritions = []
    
    for row in people_events:
        if row['event_type'] == 'Termination':
            tenure_months = int(row['tenure_months']) if row['tenure_months'] else 0
            is_early = tenure_months < 12
            
            terminations.append({
                'employee_id': row['employee_id'],
                'employee_name': row['employee_name'],
                'department': row['department'],
                'tenure_months': tenure_months,
                'is_early_attrition': is_early,
                'termination_reason': row['termination_reason'],
                'manager': row['manager']
            })
            
            if is_early:
                early_attritions.append({
                    'employee_id': row['employee_id'],
                    'employee_name': row['employee_name'],
                    'department': row['department'],
                    'tenure_months': tenure_months,
                    'termination_reason': row['termination_reason'],
                    'manager': row['manager'],
                    'is_early_attrition': is_early
                })
    
    # Group by department
    dept_attrition = defaultdict(lambda: {'total': 0, 'early': 0})
    for t in terminations:
        dept_attrition[t['department']]['total'] += 1
        if t['is_early_attrition']:
            dept_attrition[t['department']]['early'] += 1
    
    dept_summary = []
    for dept, counts in dept_attrition.items():
        early_rate = (counts['early'] / counts['total'] * 100) if counts['total'] > 0 else 0
        dept_summary.append({
            'department': dept,
            'total_terminations': counts['total'],
            'early_attritions': counts['early'],
            'early_attrition_rate': round(early_rate, 1)
        })
    
    # Group by manager
    manager_attrition = defaultdict(lambda: {'total': 0, 'early': 0})
    for t in terminations:
        manager = t['manager']
        manager_attrition[manager]['total'] += 1
        if t['is_early_attrition']:
            manager_attrition[manager]['early'] += 1
    
    manager_summary = []
    for manager, counts in manager_attrition.items():
        early_rate = (counts['early'] / counts['total'] * 100) if counts['total'] > 0 else 0
        manager_summary.append({
            'manager': manager,
            'total_terminations': counts['total'],
            'early_attritions': counts['early'],
            'early_attrition_rate': round(early_rate, 1)
        })
    
    return {
        'terminations': terminations,
        'early_attritions': early_attritions,
        'department_summary': dept_summary,
        'manager_summary': manager_summary,
        'summary': {
            'total_terminations': len(terminations),
            'total_early_attritions': len(early_attritions),
            'overall_early_attrition_rate': round((len(early_attritions) / len(terminations) * 100) if terminations else 0, 1)
        }
    }


def compute_time_to_fill(pipeline_data):
    """Calculate time-to-fill metrics by role, department, and level."""
    hired_candidates = []
    
    for row in pipeline_data:
        if row['disposition'] == 'Hired' and row['time_to_close_days']:
            try:
                time_to_fill = float(row['time_to_close_days'])
                hired_candidates.append({
                    'candidate_id': row['candidate_id'],
                    'candidate_name': row['candidate_name'],
                    'role': row['role'],
                    'department': row['department'],
                    'level': row['level'],
                    'hiring_manager': row['hiring_manager'],
                    'time_to_fill_days': time_to_fill,
                    'source': row['source']
                })
            except (ValueError, TypeError):
                continue
    
    if not hired_candidates:
        return {
            'hired_candidates': [],
            'by_department': [],
            'by_level': [],
            'by_role': [],
            'by_hiring_manager': [],
            'summary': {
                'total_hired': 0,
                'avg_time_to_fill': 0,
                'median_time_to_fill': 0,
                'min_time_to_fill': 0,
                'max_time_to_fill': 0
            }
        }
    
    # Calculate summary stats
    time_to_fills = [c['time_to_fill_days'] for c in hired_candidates]
    time_to_fills.sort()
    
    avg_time = sum(time_to_fills) / len(time_to_fills)
    median_time = time_to_fills[len(time_to_fills) // 2] if time_to_fills else 0
    
    # Group by department
    dept_ttf = defaultdict(list)
    for c in hired_candidates:
        dept_ttf[c['department']].append(c['time_to_fill_days'])
    
    dept_summary = []
    for dept, times in dept_ttf.items():
        times.sort()
        dept_summary.append({
            'department': dept,
            'count': len(times),
            'avg_time_to_fill': round(sum(times) / len(times), 1),
            'median_time_to_fill': round(times[len(times) // 2], 1)
        })
    
    # Group by level
    level_ttf = defaultdict(list)
    for c in hired_candidates:
        level_ttf[c['level']].append(c['time_to_fill_days'])
    
    level_summary = []
    for level, times in level_ttf.items():
        times.sort()
        level_summary.append({
            'level': level,
            'count': len(times),
            'avg_time_to_fill': round(sum(times) / len(times), 1),
            'median_time_to_fill': round(times[len(times) // 2], 1)
        })
    
    # Group by role
    role_ttf = defaultdict(list)
    for c in hired_candidates:
        role_ttf[c['role']].append(c['time_to_fill_days'])
    
    role_summary = []
    for role, times in role_ttf.items():
        times.sort()
        role_summary.append({
            'role': role,
            'count': len(times),
            'avg_time_to_fill': round(sum(times) / len(times), 1),
            'median_time_to_fill': round(times[len(times) // 2], 1)
        })
    
    # Group by hiring manager
    hm_ttf = defaultdict(list)
    for c in hired_candidates:
        hm_ttf[c['hiring_manager']].append(c['time_to_fill_days'])
    
    hm_summary = []
    for hm, times in hm_ttf.items():
        times.sort()
        hm_summary.append({
            'hiring_manager': hm,
            'count': len(times),
            'avg_time_to_fill': round(sum(times) / len(times), 1),
            'median_time_to_fill': round(times[len(times) // 2], 1)
        })
    
    return {
        'hired_candidates': hired_candidates,
        'by_department': sorted(dept_summary, key=lambda x: x['avg_time_to_fill'], reverse=True),
        'by_level': sorted(level_summary, key=lambda x: x['avg_time_to_fill'], reverse=True),
        'by_role': sorted(role_summary, key=lambda x: x['count'], reverse=True)[:10],
        'by_hiring_manager': sorted(hm_summary, key=lambda x: x['avg_time_to_fill'], reverse=True),
        'summary': {
            'total_hired': len(hired_candidates),
            'avg_time_to_fill': round(avg_time, 1),
            'median_time_to_fill': round(median_time, 1),
            'min_time_to_fill': round(min(time_to_fills), 1),
            'max_time_to_fill': round(max(time_to_fills), 1)
        }
    }


def compute_cost_analytics(headcount_plan, offer_log, people_events):
    """Calculate cost per hire, budget utilization, and attrition costs."""
    # Calculate cost per hire by department
    dept_costs = defaultdict(lambda: {'total_cost': 0, 'hires': 0, 'budget': 0})
    
    for row in headcount_plan:
        dept = row['department']
        budget = float(row['annual_budget_usd']) if row['annual_budget_usd'] else 0
        filled = int(row['filled_seats'])
        dept_costs[dept]['budget'] = budget
        dept_costs[dept]['hires'] = filled
    
    # Add actual compensation costs from offer log
    dept_comp = defaultdict(float)
    for row in offer_log:
        if row['offer_status'] == 'Accepted':
            dept = row['department']
            base = float(row['base_salary_usd']) if row['base_salary_usd'] else 0
            bonus = float(row['bonus_target_usd']) if row['bonus_target_usd'] else 0
            equity = float(row['equity_grant_usd']) if row['equity_grant_usd'] else 0
            signing = float(row['signing_bonus_usd']) if row['signing_bonus_usd'] else 0
            total_comp = base + bonus + equity + signing
            dept_comp[dept] += total_comp
    
    # Calculate cost per hire
    cost_summary = []
    total_budget = 0
    total_actual_cost = 0
    total_hires = 0
    
    for dept, data in dept_costs.items():
        actual_cost = dept_comp.get(dept, 0)
        hires = data['hires']
        budget = data['budget']
        cost_per_hire = round(actual_cost / hires, 0) if hires > 0 else 0
        budget_utilization = round((actual_cost / budget * 100), 1) if budget > 0 else 0
        
        total_budget += budget or 0
        total_actual_cost += actual_cost
        total_hires += hires
        
        cost_summary.append({
            'department': dept,
            'hires': hires,
            'annual_budget': budget or 0,
            'actual_cost': actual_cost,
            'cost_per_hire': cost_per_hire,
            'budget_utilization': budget_utilization
        })
    
    # Calculate attrition costs (simplified: 1.5x annual salary as replacement cost)
    attrition_costs = []
    total_attrition_cost = 0
    
    for row in people_events:
        if row['event_type'] == 'Termination':
            salary = float(row['base_salary_usd']) if row['base_salary_usd'] else 0
            replacement_cost = salary * 1.5  # Industry standard: 1.5x annual salary
            tenure_months = int(row['tenure_months']) if row['tenure_months'] else 0
            
            attrition_costs.append({
                'employee_id': row['employee_id'],
                'employee_name': row['employee_name'],
                'department': row['department'],
                'annual_salary': salary,
                'replacement_cost': round(replacement_cost, 0),
                'tenure_months': tenure_months,
                'is_early_attrition': tenure_months < 12
            })
            
            total_attrition_cost += replacement_cost
    
    # Attrition cost by department
    dept_attrition_cost = defaultdict(float)
    for ac in attrition_costs:
        dept_attrition_cost[ac['department']] += ac['replacement_cost']
    
    attrition_by_dept = []
    for dept, cost in dept_attrition_cost.items():
        attrition_by_dept.append({
            'department': dept,
            'total_attrition_cost': round(cost, 0),
            'attrition_count': len([ac for ac in attrition_costs if ac['department'] == dept])
        })
    
    return {
        'cost_per_hire': sorted(cost_summary, key=lambda x: x['cost_per_hire'], reverse=True),
        'attrition_costs': attrition_costs,
        'attrition_by_department': sorted(attrition_by_dept, key=lambda x: x['total_attrition_cost'], reverse=True),
        'summary': {
            'total_budget': total_budget,
            'total_actual_cost': total_actual_cost,
            'total_hires': total_hires,
            'overall_cost_per_hire': round(total_actual_cost / total_hires, 0) if total_hires > 0 else 0,
            'overall_budget_utilization': round((total_actual_cost / total_budget * 100), 1) if total_budget > 0 else 0,
            'total_attrition_cost': round(total_attrition_cost, 0),
            'early_attrition_cost': round(sum([ac['replacement_cost'] for ac in attrition_costs if ac['is_early_attrition']]), 0)
        }
    }


def compute_offer_decline_analysis(offer_log):
    """Analyze offer decline patterns and reasons."""
    declined_offers = []
    accepted_offers = []
    
    for row in offer_log:
        if row['offer_status'] == 'Declined':
            declined_offers.append({
                'candidate_id': row['candidate_id'],
                'candidate_name': row['candidate_name'],
                'role': row['role'],
                'department': row['department'],
                'level': row['level'],
                'base_salary': float(row['base_salary_usd']) if row['base_salary_usd'] else 0,
                'equity_grant': float(row['equity_grant_usd']) if row['equity_grant_usd'] else 0,
                'signing_bonus': float(row['signing_bonus_usd']) if row['signing_bonus_usd'] else 0,
                'decline_reason': row['decline_reason'],
                'competing_offer': row['competing_offer'] == 'True',
                'days_to_close': float(row['days_to_close']) if row['days_to_close'] else 0
            })
        elif row['offer_status'] == 'Accepted':
            accepted_offers.append({
                'candidate_id': row['candidate_id'],
                'role': row['role'],
                'department': row['department'],
                'level': row['level'],
                'base_salary': float(row['base_salary_usd']) if row['base_salary_usd'] else 0,
                'equity_grant': float(row['equity_grant_usd']) if row['equity_grant_usd'] else 0,
                'signing_bonus': float(row['signing_bonus_usd']) if row['signing_bonus_usd'] else 0
            })
    
    # Calculate average comp for accepted offers by role/level
    accepted_comp = defaultdict(list)
    for ao in accepted_offers:
        key = (ao['role'], ao['level'])
        accepted_comp[key].append(ao['base_salary'])
    
    avg_accepted_comp = {}
    for key, salaries in accepted_comp.items():
        avg_accepted_comp[key] = sum(salaries) / len(salaries)
    
    # Analyze declined offers
    decline_analysis = []
    for do in declined_offers:
        key = (do['role'], do['level'])
        avg_accepted = avg_accepted_comp.get(key, 0)
        comp_gap = do['base_salary'] - avg_accepted if avg_accepted > 0 else 0
        
        decline_analysis.append({
            'candidate_id': do['candidate_id'],
            'candidate_name': do['candidate_name'],
            'role': do['role'],
            'department': do['department'],
            'level': do['level'],
            'offered_salary': do['base_salary'],
            'avg_accepted_salary': round(avg_accepted, 0),
            'comp_gap': round(comp_gap, 0),
            'decline_reason': do['decline_reason'],
            'competing_offer': do['competing_offer'],
            'days_to_close': do['days_to_close']
        })
    
    # Group by decline reason
    reason_counts = defaultdict(int)
    for do in declined_offers:
        reason = do['decline_reason'] or 'Unknown'
        reason_counts[reason] += 1
    
    decline_reasons = []
    for reason, count in reason_counts.items():
        decline_reasons.append({
            'reason': reason,
            'count': count,
            'percentage': round((count / len(declined_offers) * 100), 1) if declined_offers else 0
        })
    
    # Competing offer impact
    with_competing = len([do for do in declined_offers if do['competing_offer']])
    without_competing = len(declined_offers) - with_competing
    
    return {
        'declined_offers': decline_analysis,
        'decline_reasons': sorted(decline_reasons, key=lambda x: x['count'], reverse=True),
        'summary': {
            'total_offers': len(offer_log),
            'total_declined': len(declined_offers),
            'total_accepted': len(accepted_offers),
            'decline_rate': round((len(declined_offers) / len(offer_log) * 100), 1) if offer_log else 0,
            'with_competing_offer': with_competing,
            'without_competing_offer': without_competing,
            'competing_offer_decline_rate': round((with_competing / len(declined_offers) * 100), 1) if declined_offers else 0
        }
    }


def validate_data_quality(pipeline_data, offer_log, people_events, headcount_plan):
    """Validate data quality and flag potential issues."""
    issues = []
    warnings = []
    
    # Check pipeline data for missing or invalid values
    for row in pipeline_data:
        if not row.get('candidate_id'):
            issues.append(f"Pipeline: Missing candidate_id for {row.get('candidate_name', 'Unknown')}")
        
        if row.get('days_in_current_stage'):
            try:
                days = int(row['days_in_current_stage'])
                if days < 0:
                    issues.append(f"Pipeline: Negative days_in_stage for {row.get('candidate_id')}")
                if days > 365:
                    warnings.append(f"Pipeline: Unusually high days_in_stage ({days}) for {row.get('candidate_id')}")
            except (ValueError, TypeError):
                issues.append(f"Pipeline: Invalid days_in_stage for {row.get('candidate_id')}")
    
    # Check offer log for compensation issues
    for row in offer_log:
        if row.get('base_salary_usd'):
            try:
                salary = float(row['base_salary_usd'])
                if salary < 0:
                    issues.append(f"Offer Log: Negative salary for {row.get('candidate_id')}")
                if salary > 1000000:
                    warnings.append(f"Offer Log: Unusually high salary (${salary:,.0f}) for {row.get('candidate_id')}")
            except (ValueError, TypeError):
                issues.append(f"Offer Log: Invalid salary for {row.get('candidate_id')}")
        
        if row.get('equity_grant_usd'):
            try:
                equity = float(row['equity_grant_usd'])
                if equity < 0:
                    issues.append(f"Offer Log: Negative equity for {row.get('candidate_id')}")
            except (ValueError, TypeError):
                issues.append(f"Offer Log: Invalid equity for {row.get('candidate_id')}")
    
    # Check people events for tenure issues
    for row in people_events:
        if row.get('tenure_months'):
            try:
                tenure = int(row['tenure_months'])
                if tenure < 0:
                    issues.append(f"People Events: Negative tenure for {row.get('employee_id')}")
                if row['event_type'] == 'Hire' and tenure != 0:
                    warnings.append(f"People Events: Hire event with tenure={tenure} for {row.get('employee_id')}")
            except (ValueError, TypeError):
                issues.append(f"People Events: Invalid tenure for {row.get('employee_id')}")
    
    # Check headcount plan for consistency
    for row in headcount_plan:
        try:
            approved = int(row['approved_headcount'])
            filled = int(row['filled_seats'])
            open_seats = int(row['open_seats'])
            
            if filled > approved:
                issues.append(f"Headcount Plan: Filled seats ({filled}) > approved ({approved}) for {row['department']} {row['level']}")
            
            if open_seats != approved - filled:
                warnings.append(f"Headcount Plan: Open seats calculation mismatch for {row['department']} {row['level']}")
        except (ValueError, TypeError):
            issues.append(f"Headcount Plan: Invalid headcount values for {row['department']} {row['level']}")
    
    return {
        'issues': issues,
        'warnings': warnings,
        'summary': {
            'total_issues': len(issues),
            'total_warnings': len(warnings),
            'data_quality_score': max(0, 100 - (len(issues) * 10) - (len(warnings) * 5))
        }
    }


def main():
    """Main function to compute all metrics."""
    # Define data paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data')
    
    # Load data
    headcount_plan = load_csv(os.path.join(data_dir, 'headcount_plan.csv'))
    offer_log = load_csv(os.path.join(data_dir, 'offer_log.csv'))
    people_events = load_csv(os.path.join(data_dir, 'people_events.csv'))
    recruiting_pipeline = load_csv(os.path.join(data_dir, 'recruiting_pipeline.csv'))
    offer_letters_dir = os.path.join(data_dir, 'offer_letters')
    
    # Compute all metrics (use default stage targets for initial load)
    default_stage_targets = {
        'Applied': 3,
        'Phone Screen': 7,
        'Technical/Assessment': 10,
        'Hiring Manager Interview': 10,
        'Final Round': 14,
        'Offer Extended': 5,
        'Offer Accepted': 5
    }
    pipeline_health = compute_pipeline_health(recruiting_pipeline, default_stage_targets)
    headcount_gaps = compute_headcount_gaps(headcount_plan, recruiting_pipeline)
    offer_funnel = compute_offer_funnel(recruiting_pipeline)
    offer_reconciliation = compute_offer_reconciliation(offer_log, offer_letters_dir)
    attrition = compute_attrition(people_events)
    time_to_fill = compute_time_to_fill(recruiting_pipeline)
    cost_analytics = compute_cost_analytics(headcount_plan, offer_log, people_events)
    offer_decline = compute_offer_decline_analysis(offer_log)
    data_quality = validate_data_quality(recruiting_pipeline, offer_log, people_events, headcount_plan)
    
    # Combine all results
    results = {
        'pipeline_health': pipeline_health,
        'headcount_gaps': headcount_gaps,
        'offer_funnel': offer_funnel,
        'offer_reconciliation': offer_reconciliation,
        'attrition': attrition,
        'time_to_fill': time_to_fill,
        'cost_analytics': cost_analytics,
        'offer_decline': offer_decline,
        'data_quality': data_quality
    }
    
    return results


if __name__ == '__main__':
    results = main()
    print(json.dumps(results, indent=2))
