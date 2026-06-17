#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove ALL CJK characters from Thai translation chapter files."""

import re
import json

files = [
    'novels/global-descent/chapters/0133.json',
]

# CJK character ranges
CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')

for fpath in files:
    # Read raw content
    with open(fpath, 'r', encoding='utf-8') as f:
        raw = f.read()
    
    # Fix unescaped double quotes inside JSON string values
    # Look for patterns like: "text": "..."..."  
    # These happen when a Thai text contains a regular double quote that wasn't escaped
    # Strategy: find "text": " blocks and fix inner unescaped quotes
    
    # For ch 133 specific issue: "「ให้ตาย... เพลิงร้าย เหี่ยวเฉาวิญญาณ นั่นสกิลของปีศาจเมื่อกี้?"」
    # The " before 」 closes the JSON string prematurely. Replace inner " with escaped \"
    
    # More robust: process line by line for text values
    lines = raw.split('\n')
    fixed_lines = []
    for line in lines:
        # Find lines with "text": " that have unescaped quotes in the value
        if '"text": "' in line and line.count('"') > 4:
            # Extract the text value between first "text": " and the last "
            prefix = '"text": "'
            idx = line.find(prefix)
            if idx >= 0:
                start = idx + len(prefix)
                # The value should end with the last " before the comma/end
                # But if there are inner quotes, this breaks
                # Find the closing pattern: 「" or 」" or ?"
                value_part = line[start:]
                # Check if there's an unescaped quote by trying to find where the
                # JSON string actually ends
                
                # Escape interior double quotes that aren't at the end of the string
                # Look for " that isn't the last " before a JSON delimiter
                result = []
                i = 0
                in_value = True
                while i < len(value_part):
                    ch = value_part[i]
                    if ch == '"':
                        # Check if this is likely the closing quote
                        rest = value_part[i+1:]
                        if rest.startswith(',') or rest.startswith('\n') or rest.startswith(' '):
                            result.append(ch)
                            in_value = False
                            result.append(rest)
                            break
                        elif rest.startswith('」'):
                            # This could be a Thai quote inside the string
                            # Escape it
                            result.append('\\"')
                        else:
                            result.append(ch)
                    else:
                        result.append(ch)
                    i += 1
                
                if not in_value:
                    fixed_line = line[:start] + ''.join(result)
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    raw_fixed = '\n'.join(fixed_lines)
    
    # Try parsing JSON
    try:
        data = json.loads(raw_fixed)
    except json.JSONDecodeError as e:
        print(f'{fpath}: Still JSON broken - {e}')
        print(f'Attempting brute force fix...')
        # Brute force: escape all interior double quotes in text values
        # Find all "text": "..." patterns and re-parse
        
        # Simpler approach: find all text values and properly escape them
        import ast
        
        # Use regex to find text values and fix them
        def fix_text_value(match):
            prefix = match.group(1)
            value = match.group(2)
            # Escape any unescaped double quotes inside the value
            escaped_value = value.replace('\\"', '\x00').replace('"', '\\"').replace('\x00', '\\"')
            return f'{prefix}"{escaped_value}"'
        
        # Match "text": "..." patterns where ... might contain unescaped quotes
        # This is a simplified approach
        pattern = re.compile(r'("text":\s*")([^"]*(?:"[^"]*)*)")')
        raw_fixed2 = pattern.sub(fix_text_value, raw)
        
        try:
            data = json.loads(raw_fixed2)
            print(f'{fpath}: Fixed with brute force!')
        except json.JSONDecodeError as e2:
            print(f'{fpath}: Still broken - {e2}')
            continue
    
    total_removed = 0
    for block in data['blocks']:
        if block['type'] in ('narration', 'dialogue', 'system', 'end'):
            original = block['text']
            cleaned = CJK_RE.sub('', original)
            # Clean up whitespace artifacts from CJK removal
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned != original:
                block['text'] = cleaned
                total_removed += 1
    
    # Save fixed version
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Count remaining CJK for verification
    content = json.dumps(data, ensure_ascii=False)
    remaining = CJK_RE.findall(content)
    
    print(f'{fpath}: {total_removed} blocks cleaned, remaining CJK: {len(remaining)}')
    if remaining:
        print(f'  Remaining: {set(remaining)}')

print('\nDone!')
