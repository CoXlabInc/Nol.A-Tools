import os
import json

def load(config_file):
    config = {}
    if os.path.exists(config_file):
        with open(config_file) as f:
            config = json.load(f)
    return config

def save(config, config_file):
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f)
        
