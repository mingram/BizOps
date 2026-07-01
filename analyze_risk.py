#!/usr/bin/env python3
import csv
from collections import defaultdict

# Load headcount plan
with open('c:/Users/Max/Downloads/Cognition Case/data/headcount_plan.csv', 'r') as f:
    headcount = list(csv.DictReader(f))

# Load pipeline
with open('c:/Users/Max/Downloads/Cognition Case/data/recruiting_pipeline.csv', 'r') as f:
    pipeline = list(csv.DictReader(f))

# Count active pipeline by (department, level)
pipeline_counts = defaultdict(int)
for row in pipeline:
    if row['disposition'] == 'Active':
        key = (row['department'], row['level'])
        pipeline_counts[key] += 1

# Find critical risks
critical_risks = []
for row in headcount:
    dept = row['department']
    level = row['level']
    open_seats = int(row['open_seats'])
    priority = row['priority']
    key = (dept, level)
    active_pipeline = pipeline_counts.get(key, 0)
    
    if open_seats > 0 and active_pipeline == 0 and priority == 'High':
        critical_risks.append({
            'department': dept,
            'level': level,
            'open_seats': open_seats,
            'priority': priority
        })

print('Critical Risks Found:')
for risk in critical_risks:
    print(f"  {risk['department']} {risk['level']}: {risk['open_seats']} open seats, {risk['priority']} priority, 0 active pipeline")

print('\nAll High Priority Open Seats with Pipeline Status:')
for row in headcount:
    dept = row['department']
    level = row['level']
    open_seats = int(row['open_seats'])
    priority = row['priority']
    key = (dept, level)
    active_pipeline = pipeline_counts.get(key, 0)
    
    if open_seats > 0 and priority == 'High':
        print(f"  {dept} {level}: {open_seats} open seats, {active_pipeline} active pipeline")
