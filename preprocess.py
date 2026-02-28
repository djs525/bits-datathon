import pandas as pd
import re
import json
import random
from datetime import datetime

# Synthetic Slack mapping config
CHANNELS = ["#general", "#engineering", "#marketing", "#sales", "#hr", "#product"]

def parse_message(message_str):
    """
    Parses the raw email message string to extract headers and body.
    """
    headers = {}
    lines = message_str.split('\n')
    body_start_idx = 0
    
    for i, line in enumerate(lines):
        if not line:  # First empty line separates headers from body
            body_start_idx = i + 1
            break
        
        # Simple header parsing
        match = re.match(r'^([\w-]+): (.*)$', line)
        if match:
            headers[match.group(1)] = match.group(2)
            
    body = '\n'.join(lines[body_start_idx:]).strip()
    return headers, body

def preprocess_emails(file_path, output_path, sample_size=1000):
    # Using on_bad_lines='skip' to handle malformed rows in the large Enron dataset
    df = pd.read_csv(file_path, nrows=sample_size, on_bad_lines='skip')
    processed_data = []
    
    for index, row in df.iterrows():
        try:
            headers, body = parse_message(row['message'])
            
            # Extract basic info
            sender = headers.get('From', 'unknown')
            date_str = headers.get('Date', '')
            subject = headers.get('Subject', '')
            
            # Map to a synthetic channel
            channel = random.choice(CHANNELS)
            
            # Build the Slack-like message object
            msg = {
                "id": index,
                "timestamp": date_str,
                "user": sender,
                "channel": channel,
                "text": f"Subject: {subject}\n\n{body}",
                "metadata": {
                    "raw_headers": headers
                }
            }
            processed_data.append(msg)
        except Exception as e:
            print(f"Error processing row {index}: {e}")
            continue
            
    with open(output_path, 'w') as f:
        json.dump(processed_data, f, indent=2)
    
    print(f"Processed {len(processed_data)} messages and saved to {output_path}")

if __name__ == "__main__":
    # Reading from the original large file with nrows=2000 to avoid sampling issues
    preprocess_emails('emails.csv', 'slack_data.json', sample_size=2000)
