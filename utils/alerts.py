import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from utils.logger import log

class AlertManager:
    def __init__(self, config):
        self.config = config
        self.alert_config = config.get('alerts', {})

    def send_trade_alert(self, trade_info):
        """Send alert when trade is executed."""
        message = f"""
🔥 TRADE EXECUTED 🔥

Strategy: {trade_info.get('strategy', 'Unknown')}
Direction: {trade_info.get('direction', 'Unknown')}
Underlying: {trade_info.get('underlying', 'Unknown')}
Entry Price: {trade_info.get('entry_price', 'Unknown')}
Max Risk: ₹{trade_info.get('max_risk', 'Unknown')}
Confidence: {trade_info.get('confidence', 'Unknown')}%

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self._send_alert("Trade Executed", message, level="INFO")

    def send_risk_alert(self, risk_info):
        """Send alert for risk management events."""
        message = f"""
⚠️ RISK ALERT ⚠️

Event: {risk_info.get('event', 'Unknown')}
Current Value: {risk_info.get('current_value', 'Unknown')}
Limit: {risk_info.get('limit', 'Unknown')}
Action Taken: {risk_info.get('action', 'None')}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self._send_alert("Risk Alert", message, level="WARNING")

    def send_critical_alert(self, message):
        """Send critical system alert."""
        critical_message = f"""
🚨 CRITICAL SYSTEM ALERT 🚨

{message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

IMMEDIATE ATTENTION REQUIRED!
        """
        
        self._send_alert("CRITICAL ALERT", critical_message, level="CRITICAL")

    def send_pnl_update(self, pnl_info):
        """Send P&L update."""
        status_emoji = "📈" if pnl_info.get('daily_pnl', 0) > 0 else "📉"
        
        message = f"""
{status_emoji} DAILY P&L UPDATE {status_emoji}

Daily P&L: ₹{pnl_info.get('daily_pnl', 0):,.2f}
Total Positions: {pnl_info.get('position_count', 0)}
Portfolio Delta: {pnl_info.get('portfolio_delta', 0):.2f}
Portfolio Theta: ₹{pnl_info.get('portfolio_theta', 0):.2f}

Best Performer: {pnl_info.get('best_trade', 'None')}
Worst Performer: {pnl_info.get('worst_trade', 'None')}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self._send_alert("P&L Update", message, level="INFO")

    def _send_alert(self, subject, message, level="INFO"):
        """Send alert via configured channels."""
        try:
            # Email alerts
            if self.alert_config.get('email_enabled', False):
                self._send_email_alert(subject, message, level)
                
            # Telegram alerts  
            if self.alert_config.get('telegram_enabled', False):
                self._send_telegram_alert(f"{subject}\n\n{message}")
                
            # Console log
            if level == "CRITICAL":
                log.critical(f"{subject}: {message}")
            elif level == "WARNING":
                log.warning(f"{subject}: {message}")
            else:
                log.info(f"{subject}: {message}")
                
        except Exception as e:
            log.error(f"Error sending alert: {e}")

    def _send_email_alert(self, subject, message, level):
        """Send email alert."""
        try:
            email_address = self.alert_config.get('email_address')
            if not email_address:
                return

            # Configure your SMTP settings here
            smtp_server = "smtp.gmail.com"  # Change as needed
            smtp_port = 587
            sender_email = "your_bot_email@gmail.com"  # Configure this
            sender_password = "your_app_password"      # Configure this

            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email_address
            msg['Subject'] = f"ProTraderBot - {subject}"

            msg.attach(MIMEText(message, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()

            log.debug(f"Email alert sent: {subject}")

        except Exception as e:
            log.error(f"Error sending email alert: {e}")

    def _send_telegram_alert(self, message):
        """Send Telegram alert."""
        try:
            bot_token = self.alert_config.get('telegram_bot_token')
            chat_id = self.alert_config.get('telegram_chat_id')
            
            if not bot_token or not chat_id:
                return

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                log.debug("Telegram alert sent successfully")
            else:
                log.error(f"Telegram alert failed: {response.status_code}")

        except Exception as e:
            log.error(f"Error sending Telegram alert: {e}")
