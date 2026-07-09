#!/usr/bin/env python3
import csv
import os
from collections import defaultdict

# Define data paths relative to this script
base_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(base_dir, 'data')

# Load headcount plan
with open(os.path.join(data_dir, 'headcount_plan.csv'), 'r', encoding='utf-8') as f:
    headcount = list(csv.DictReader(f))

# Load pipeline
with open(os.path.join(data_dir, 'recruiting_pipeline.csv'), 'r', encoding='utf-8') as f:
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
