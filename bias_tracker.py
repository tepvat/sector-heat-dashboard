import json
import os
from datetime import datetime, timedelta

class BiasTracker:
    def __init__(self):
        self.data_file = 'bias_data.json'
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                'biases': {},
                'setup_scores': {}
            }
            self.save_data()

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add_bias(self, token, bias, user_id):
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.data['biases']:
            self.data['biases'][today] = {}
        
        self.data['biases'][today][token] = {
            'bias': bias,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        }
        self.save_data()

    def add_setup_score(self, token, score, user_id):
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.data['setup_scores']:
            self.data['setup_scores'][today] = {}
        
        self.data['setup_scores'][today][token] = {
            'score': score,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        }
        self.save_data()

    def get_weekly_summary(self):
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        
        summary = {
            'biases': {},
            'setup_scores': {}
        }
        
        for date, data in self.data['biases'].items():
            if datetime.strptime(date, '%Y-%m-%d') >= week_ago:
                summary['biases'][date] = data
                
        for date, data in self.data['setup_scores'].items():
            if datetime.strptime(date, '%Y-%m-%d') >= week_ago:
                summary['setup_scores'][date] = data
                
        return summary

    def format_weekly_summary(self):
        summary = self.get_weekly_summary()
        message = "*Weekly Bias & Setup Score Summary*\n\n"
        
        # Format biases
        message += "*Biases:*\n"
        for date, data in sorted(summary['biases'].items()):
            message += f"\n{date}:\n"
            for token, info in data.items():
                message += f"{token}: {info['bias']}\n"
        
        # Format setup scores
        message += "\n*Setup Scores:*\n"
        for date, data in sorted(summary['setup_scores'].items()):
            message += f"\n{date}:\n"
            for token, info in data.items():
                message += f"{token}: {info['score']}\n"
        
        return message 